#!/usr/bin/env python3
"""One-shot AWS deployment script for the Autonomous Diagnostic Pipeline.

Run with credentials that have:
  - s3:CreateBucket, s3:PutBucketPolicy
  - iam:CreateRole, iam:AttachRolePolicy, iam:PutRolePolicy, iam:PassRole
  - lambda:CreateFunction, lambda:UpdateFunctionCode, lambda:GetFunction
  - states:CreateStateMachine, states:UpdateStateMachine
  - bedrock:InvokeModel (for embeddings)

Usage:
  AWS_PROFILE=admin python aws/deploy.py
  # or with explicit keys:
  AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... python aws/deploy.py

The script writes discovered ARNs back into .env automatically.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import boto3

# ── Configuration ─────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCOUNT_ID: str = ""  # filled in at runtime

BUCKET_NAME_TEMPLATE = "airbyte-diagnostic-memory-{account_id}"
STATE_MACHINE_NAME = "DiagnosticPipeline"

LAMBDA_FUNCTIONS = [
    ("DiagnosticIngestData",       "pipeline_handlers.ingest_data",        256,  60),
    ("DiagnosticBuildContext",     "pipeline_handlers.build_agent_context", 512,  120),
    ("DiagnosticSyncGraph",        "pipeline_handlers.sync_graph_context",  512,  300),
    ("DiagnosticRunDiagnosis",     "pipeline_handlers.run_diagnosis",       512,  600),
    ("DiagnosticLogMemory",        "pipeline_handlers.log_memory",          256,  30),
]

LAMBDA_ROLE_NAME = "DiagnosticLambdaExecutionRole"
SFN_ROLE_NAME    = "DiagnosticStepFunctionsRole"


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def get_account_id(sts) -> str:
    return sts.get_caller_identity()["Account"]


# ── S3 ─────────────────────────────────────────────────────────────────────────

def create_s3_bucket(s3, bucket_name: str) -> str:
    print(f"\n[S3] Creating bucket: {bucket_name}")
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        log("created")
    except (s3.exceptions.BucketAlreadyOwnedByYou,
            s3.exceptions.from_code("BucketAlreadyOwnedByYou").__class__):
        log("already exists (owned by you) — skipping")
    except Exception as exc:
        if "BucketAlreadyOwnedByYou" in str(exc):
            log("already exists (owned by you) — skipping")
        elif "BucketAlreadyExists" in str(exc):
            log("name taken globally — choose a different name and re-run")
            raise
        else:
            raise
    # Block public access
    s3.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    log("public access blocked")
    return bucket_name


# ── IAM ────────────────────────────────────────────────────────────────────────

def ensure_lambda_role(iam, bucket_name: str) -> str:
    print(f"\n[IAM] Lambda execution role: {LAMBDA_ROLE_NAME}")
    trust = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                       "Action": "sts:AssumeRole"}],
    }
    try:
        role = iam.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Execution role for Diagnostic Pipeline Lambda functions",
        )
        role_arn = role["Role"]["Arn"]
        log(f"created: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=LAMBDA_ROLE_NAME)["Role"]["Arn"]
        log(f"already exists: {role_arn}")

    # Attach managed policies
    managed = [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        "arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
    ]
    for arn in managed:
        try:
            iam.attach_role_policy(RoleName=LAMBDA_ROLE_NAME, PolicyArn=arn)
            log(f"attached: {arn.split('/')[-1]}")
        except Exception:
            pass

    # Inline policy for S3 + Step Functions
    inline = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
            },
        ],
    }
    iam.put_role_policy(
        RoleName=LAMBDA_ROLE_NAME,
        PolicyName="DiagnosticS3Access",
        PolicyDocument=json.dumps(inline),
    )
    log("inline S3 policy applied")
    # Wait for role to propagate
    time.sleep(10)
    return role_arn


def ensure_sfn_role(iam, lambda_arns: list[str]) -> str:
    print(f"\n[IAM] Step Functions execution role: {SFN_ROLE_NAME}")
    trust = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "states.amazonaws.com"},
                       "Action": "sts:AssumeRole"}],
    }
    try:
        role = iam.create_role(
            RoleName=SFN_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Execution role for Diagnostic Pipeline Step Functions state machine",
        )
        role_arn = role["Role"]["Arn"]
        log(f"created: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=SFN_ROLE_NAME)["Role"]["Arn"]
        log(f"already exists: {role_arn}")

    inline = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": lambda_arns,
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogDelivery",
                           "logs:PutLogEvents", "logs:DescribeLogGroups"],
                "Resource": "*",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=SFN_ROLE_NAME,
        PolicyName="DiagnosticSFNPolicy",
        PolicyDocument=json.dumps(inline),
    )
    log("inline Lambda invoke policy applied")
    return role_arn


# ── Lambda package ─────────────────────────────────────────────────────────────

def build_lambda_zip() -> bytes:
    """Build a minimal zip: handler file + installed package (no heavy deps — they come from layer)."""
    print("\n[Lambda] Building deployment zip")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Handler
        handler_path = REPO_ROOT / "aws" / "handlers" / "pipeline_handlers.py"
        zf.write(handler_path, "pipeline_handlers.py")
        log(f"added handler: {handler_path.name}")

        # Package source (our library)
        pkg_root = REPO_ROOT / "src" / "silo_smasher"
        for py_file in pkg_root.rglob("*.py"):
            arcname = "silo_smasher" + str(py_file)[len(str(pkg_root)):]
            zf.write(py_file, arcname)
        log("added package source")

        # Minimal deps not in Lambda runtime: openai, neo4j, requests, google-genai, airbyte-api
        # Install them into a temp dir and include
        with tempfile.TemporaryDirectory() as tmp:
            deps = [
                "openai>=1.0.0",
                "neo4j==5.28.2",
                "requests==2.32.5",
                "google-genai==1.65.0",
                "airbyte-api==0.53.0",
                "python-dotenv==1.2.1",
            ]
            log(f"pip-installing {len(deps)} deps into zip ...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--target", tmp, *deps],
                check=True,
            )
            for f in Path(tmp).rglob("*"):
                if f.is_file() and not any(p in str(f) for p in [".dist-info", "__pycache__"]):
                    zf.write(f, str(f)[len(tmp) + 1:])
            log("deps packed")

    size_mb = len(buf.getvalue()) / 1024 / 1024
    log(f"zip size: {size_mb:.1f} MB")
    return buf.getvalue()


def deploy_lambda(lam, iam_role_arn: str, zip_bytes: bytes, env_vars: dict[str, str]) -> dict[str, str]:
    """Create or update all Lambda functions. Returns {name: arn}."""
    arns: dict[str, str] = {}

    for func_name, handler, memory, timeout in LAMBDA_FUNCTIONS:
        print(f"\n[Lambda] {func_name}")
        try:
            resp = lam.create_function(
                FunctionName=func_name,
                Runtime="python3.13",
                Role=iam_role_arn,
                Handler=handler,
                Code={"ZipFile": zip_bytes},
                Description=f"Diagnostic Pipeline — {handler.split('.')[-1]}",
                Timeout=timeout,
                MemorySize=memory,
                Environment={"Variables": env_vars},
            )
            arn = resp["FunctionArn"]
            log(f"created: {arn}")
        except lam.exceptions.ResourceConflictException:
            # Update existing
            lam.update_function_code(FunctionName=func_name, ZipFile=zip_bytes)
            lam.update_function_configuration(
                FunctionName=func_name,
                Timeout=timeout,
                MemorySize=memory,
                Environment={"Variables": env_vars},
            )
            arn = lam.get_function(FunctionName=func_name)["Configuration"]["FunctionArn"]
            log(f"updated: {arn}")
        arns[func_name] = arn

    return arns


# ── Step Functions ─────────────────────────────────────────────────────────────

def deploy_state_machine(sfn, sfn_role_arn: str, lambda_arns: dict[str, str]) -> str:
    print(f"\n[Step Functions] State machine: {STATE_MACHINE_NAME}")

    sm_def_path = REPO_ROOT / "aws" / "step_functions" / "state_machine.json"
    definition = sm_def_path.read_text()

    replacements = {
        "${IngestDataFunctionArn}":   lambda_arns["DiagnosticIngestData"],
        "${BuildContextFunctionArn}": lambda_arns["DiagnosticBuildContext"],
        "${SyncGraphFunctionArn}":    lambda_arns["DiagnosticSyncGraph"],
        "${RunDiagnosisFunctionArn}": lambda_arns["DiagnosticRunDiagnosis"],
        "${LogMemoryFunctionArn}":    lambda_arns["DiagnosticLogMemory"],
    }
    for placeholder, arn in replacements.items():
        definition = definition.replace(placeholder, arn)

    try:
        resp = sfn.create_state_machine(
            name=STATE_MACHINE_NAME,
            definition=definition,
            roleArn=sfn_role_arn,
            type="STANDARD",
        )
        sm_arn = resp["stateMachineArn"]
        log(f"created: {sm_arn}")
    except sfn.exceptions.StateMachineAlreadyExists:
        existing = [
            sm for sm in sfn.list_state_machines()["stateMachines"]
            if sm["name"] == STATE_MACHINE_NAME
        ]
        sm_arn = existing[0]["stateMachineArn"]
        sfn.update_state_machine(stateMachineArn=sm_arn, definition=definition, roleArn=sfn_role_arn)
        log(f"updated: {sm_arn}")

    return sm_arn


# ── .env updater ───────────────────────────────────────────────────────────────

def update_env_file(updates: dict[str, str]) -> None:
    env_path = REPO_ROOT / ".env"
    lines = env_path.read_text().splitlines()
    updated = set()
    new_lines = []
    for line in lines:
        key = line.split("=", 1)[0].strip().lstrip("#").strip()
        if key in updates:
            new_lines.append(f'{key}="{updates[key]}"')
            updated.add(key)
        else:
            new_lines.append(line)
    # Append any keys not already in the file
    for key, val in updates.items():
        if key not in updated:
            new_lines.append(f'{key}="{val}"')
    env_path.write_text("\n".join(new_lines) + "\n")
    print(f"\n[.env] Updated: {', '.join(updates.keys())}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    print("=" * 60)
    print("Autonomous Diagnostic Pipeline — AWS Deployment")
    print("=" * 60)

    session = boto3.Session(region_name=REGION)
    sts = session.client("sts")
    s3  = session.client("s3")
    iam = session.client("iam")
    lam = session.client("lambda")
    sfn = session.client("stepfunctions")

    global ACCOUNT_ID
    ACCOUNT_ID = get_account_id(sts)
    print(f"\nAccount : {ACCOUNT_ID}")
    print(f"Region  : {REGION}")

    bucket_name = BUCKET_NAME_TEMPLATE.format(account_id=ACCOUNT_ID)

    # 1. S3
    create_s3_bucket(s3, bucket_name)

    # 2. Lambda role (needs bucket name for inline policy)
    lambda_role_arn = ensure_lambda_role(iam, bucket_name)

    # 3. Build zip & collect env vars to pass to Lambda
    # Lambda keys must match [a-zA-Z][a-zA-Z0-9_]+ and values must be strings.
    import re as _re
    _valid_key = _re.compile(r'^[a-zA-Z][a-zA-Z0-9_]+$')
    _app_prefixes = (
        "OPENAI_", "GEMINI_", "NEO4J_", "BEDROCK_",
        "SENSO_", "FASTINO_", "YUTORI_", "NUMERIC_", "TAVILY_",
        "MODULATE_", "AIRBYTE_", "ORCHESTRATOR_",
        "AWS_S3_", "AWS_STEP_",  # only our custom AWS_ vars, not the reserved ones
    )
    # Lambda reserves AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.
    _lambda_reserved = {
        "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN",
        "AWS_EXECUTION_ENV", "AWS_LAMBDA_FUNCTION_NAME", "AWS_LAMBDA_FUNCTION_MEMORY_SIZE",
        "AWS_LAMBDA_FUNCTION_VERSION", "AWS_LAMBDA_LOG_GROUP_NAME",
        "AWS_LAMBDA_LOG_STREAM_NAME", "AWS_LAMBDA_RUNTIME_API",
    }
    zip_bytes = build_lambda_zip()
    env_vars = {
        k: str(v)
        for k, v in os.environ.items()
        if _valid_key.match(k)
        and k not in _lambda_reserved
        and (k.startswith(_app_prefixes) or k in {"PORT", "LAMBDA_TMP_ROOT"})
    }

    # 4. Deploy Lambda functions
    lambda_arns = deploy_lambda(lam, lambda_role_arn, zip_bytes, env_vars)

    # 5. Step Functions role (needs Lambda ARNs)
    sfn_role_arn = ensure_sfn_role(iam, list(lambda_arns.values()))

    # 6. State machine
    sm_arn = deploy_state_machine(sfn, sfn_role_arn, lambda_arns)

    # 7. Write ARNs back to .env
    update_env_file({
        "AWS_S3_MEMORY_BUCKET": bucket_name,
        "AWS_STEP_FUNCTIONS_STATE_MACHINE_ARN": sm_arn,
    })

    print("\n" + "=" * 60)
    print("Deployment complete!")
    print("=" * 60)
    print(f"  S3 bucket  : {bucket_name}")
    print(f"  State machine: {sm_arn}")
    print("\nLambda functions:")
    for name, arn in lambda_arns.items():
        print(f"  {name}: {arn}")
    print("\nNext: push to GitHub and connect to Render (see render.yaml)")
    print("      Set secret env vars in the Render dashboard.")


if __name__ == "__main__":
    main()
