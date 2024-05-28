# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
from pathlib import Path

from aws_cdk import Aws, RemovalPolicy, Duration
from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3,
    aws_events as events,
    aws_glue as glue,
    aws_kms as kms,
    aws_events_targets as targets,
    aws_lambda,
    aws_datasync as datasync,
)
from aws_cdk.aws_lambda import LayerVersion, Code, Runtime
from constructs import Construct

from aws_solutions.cdk.aws_lambda.python.function import SolutionsPythonFunction
from aws_solutions.cdk.aws_lambda.layers.aws_lambda_powertools import PowertoolsLayer
from aws_lambda_layers.aws_solutions.layer import SolutionsLayer
from .prebid_artifacts_constructs import ArtifactsManager
import prebid_server.stack_constants as globals


class GlueEtl(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        artifacts_construct: ArtifactsManager,
        script_file_name: str,
        source_bucket: s3.Bucket,
        datasync_task: datasync.CfnTask,
    ):
        super().__init__(scope, id)

        self.id = id
        self._resource_prefix = Aws.STACK_NAME
        self.artifacts_construct = artifacts_construct
        self.artifacts_bucket = artifacts_construct.bucket
        self.file_name = script_file_name
        self.source_bucket = source_bucket
        self.datasync_task = datasync_task

        self.GLUE_RESOURCE_PREFIX = f"{Aws.STACK_NAME}-{Aws.REGION}-{self.id.lower()}"
        self.GLUE_JOB_NAME = f"{self.GLUE_RESOURCE_PREFIX}-job"
        self.GLUE_DATABASE_NAME = f"{self.GLUE_RESOURCE_PREFIX}-database"
        self.GLUE_WORKFLOW_NAME = f"{self.GLUE_RESOURCE_PREFIX}-workflow"
        self.S3_READ_ACTIONS = ["s3:GetObject", "s3:ListBucket"]
        self.S3_CONDITIONS = {
            "StringEquals": {"aws:ResourceAccount": [f"{Aws.ACCOUNT_ID}"]}
        }
        fp = Path(__file__).absolute().parents[1] / "prebid_server"
        with open(f"{fp}/prebid_metrics_schema.json") as f:
            self.TABLE_SCHEMA_MAP = json.load(f)

        self._create_lamda_layer()
        self.output_bucket = self._create_output_bucket()
        self._create_glue_database()
        self.glue_job = self._create_glue_job()
        self.lambda_function = self._create_glue_job_trigger()

    def _create_lamda_layer(self):
        self.powertools_layer = PowertoolsLayer.get_or_create(self)
        self.metrics_layer = LayerVersion(
            self,
            "metrics-layer",
            code=Code.from_asset(
                path=os.path.join(
                    f"{Path(__file__).parents[1]}", "aws_lambda_layers/metrics_layer/"
                )
            ),
            layer_version_name=f"{self._resource_prefix}-metrics-layer",
            compatible_runtimes=[Runtime.PYTHON_3_11],
        )

    def _create_output_bucket(self) -> s3.Bucket:
        """
        This function creates the S3 Bucket where Glue outputs transformed metric files
        """
        glue_bucket_key = kms.Key(
            self,
            id="BucketKey",
            description="Metrics ETL Bucket Key",
            enable_key_rotation=True,
            pending_window=Duration.days(30),
            removal_policy=RemovalPolicy.RETAIN,
        )
        kms_bucket_policy = iam.PolicyStatement(
            sid="Allow access to Metrics ETL Bucket",
            principals=[
                iam.ServicePrincipal("s3.amazonaws.com"),
                iam.ServicePrincipal("glue.amazonaws.com"),
            ],
            effect=iam.Effect.ALLOW,
            actions=[
                "kms:Encrypt",
                "kms:Decrypt",
                "kms:ReEncrypt*",
                "kms:GenerateDataKey*",
                "kms:CreateGrant",
                "kms:DescribeKey",
            ],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "aws:SourceAccount": [f"{Aws.ACCOUNT_ID}"],
                }
            },
        )
        glue_bucket_key.add_to_resource_policy(kms_bucket_policy)
        bucket = s3.Bucket(
            self,
            id="Bucket",
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
            access_control=s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption_key=glue_bucket_key,
            removal_policy=RemovalPolicy.RETAIN,
            enforce_ssl=True,
            object_lock_enabled=True,
            versioned=True,
        )
        return bucket

    def _create_glue_database(self) -> None:
        """
        This function creates the Glue Database and Tables to catalog the transformed metrics in S3
        """
        # Create glue database
        database = glue.CfnDatabase(
            self,
            "Database",
            catalog_id=Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=self.GLUE_DATABASE_NAME
            ),
        )

        # Iterate over the metrics schema to create the tables in Glue Catalog with the proper datatypes
        for table_name, schema in self.TABLE_SCHEMA_MAP.items():
            table_columns = []
            for column_name, data_type in schema.items():
                col = glue.CfnTable.ColumnProperty(name=column_name, type=data_type)
                table_columns.append(col)

            table = glue.CfnTable(
                self,
                f"{table_name}Table",
                catalog_id=Aws.ACCOUNT_ID,
                database_name=self.GLUE_DATABASE_NAME,
                table_input=glue.CfnTable.TableInputProperty(
                    name=table_name.lower(),
                    partition_keys=[
                        glue.CfnTable.ColumnProperty(name="year_month", type="string")
                    ],
                    table_type="EXTERNAL_TABLE",
                    storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                        columns=table_columns,
                        compressed=True,
                        location=f"s3://{self.output_bucket.bucket_name}/type={table_name.lower()}/",
                        stored_as_sub_directories=True,
                        parameters={"classification": "parquet"},
                        input_format="org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                        output_format="org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                        serde_info=glue.CfnTable.SerdeInfoProperty(
                            name="ParquetHiveSerDe",
                            serialization_library="org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
                        ),
                    ),
                ),
            )

            table.node.add_dependency(database)

    def _create_glue_job(self) -> glue.CfnJob:
        """
        This function creates an IAM Role for the Glue Job to assume during execution
        """
        # Create role for the glue job
        glue_job_role = iam.Role(
            self,
            "JobRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
        )

        # Iterate over the metrics schema to get all the table names that Glue will need IAM permission to access
        glue_resources = [
            f"arn:aws:glue:{Aws.REGION}:{Aws.ACCOUNT_ID}:table/{self.GLUE_DATABASE_NAME}/{table_name.lower()}"
            for table_name in self.TABLE_SCHEMA_MAP.keys()
        ]
        glue_resources.extend(
            [
                f"arn:aws:glue:{Aws.REGION}:{Aws.ACCOUNT_ID}:catalog",
                f"arn:aws:glue:{Aws.REGION}:{Aws.ACCOUNT_ID}:database/{self.GLUE_DATABASE_NAME}",
            ]
        )

        # Create policy for the glue job role
        glue_job_policy = iam.Policy(
            self,
            "JobPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=self.S3_READ_ACTIONS,
                    resources=[
                        self.artifacts_bucket.bucket_arn,
                        self.source_bucket.bucket_arn,
                        self.output_bucket.bucket_arn,
                        f"{self.artifacts_bucket.bucket_arn}/*",
                        f"{self.source_bucket.bucket_arn}/*",
                        f"{self.output_bucket.bucket_arn}/*",
                    ],
                    conditions=self.S3_CONDITIONS,
                ),
                iam.PolicyStatement(
                    actions=[
                        "s3:PutObject",
                    ],
                    resources=[
                        self.output_bucket.bucket_arn,
                        f"{self.output_bucket.bucket_arn}/*",
                    ],
                    conditions=self.S3_CONDITIONS,
                ),
                iam.PolicyStatement(
                    actions=[
                        "glue:GetTable",
                        "glue:GetDatabase",
                        "glue:BatchCreatePartition",
                        "glue:CreatePartition",
                        "glue:GetPartition",
                        "glue:GetPartitions",
                        "glue:UpdatePartition",
                        "glue:DeletePartition",
                        "glue:BatchDeletePartition",
                        "glue:BatchGetPartition",
                    ],
                    resources=glue_resources,
                ),
                iam.PolicyStatement(
                    actions=[
                        "athena:StartQueryExecution",
                    ],
                    resources=[
                        f"arn:aws:athena:{Aws.REGION}:{Aws.ACCOUNT_ID}:workgroup/*"
                    ],
                ),
                iam.PolicyStatement(
                    actions=["s3:GetBucketLocation", "s3:PutObject"],
                    resources=[
                        self.artifacts_bucket.bucket_arn,
                        f"{self.artifacts_bucket.bucket_arn}/*",
                    ],
                    conditions=self.S3_CONDITIONS,
                ),
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=[
                        f"arn:{Aws.PARTITION}:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws-glue/*"
                    ],
                ),
                iam.PolicyStatement(
                    actions=[
                        "cloudwatch:PutMetricData",
                    ],
                    resources=[
                        "*"  # NOSONAR
                    ],
                ),
            ],
        )

        glue_job_role.attach_inline_policy(glue_job_policy)
        glue_job_policy.node.add_dependency(self.artifacts_bucket)
        glue_job_policy.node.add_dependency(self.source_bucket)
        glue_job_policy.node.add_dependency(self.output_bucket)
        self.artifacts_bucket.encryption_key.grant_encrypt_decrypt(glue_job_role)
        self.source_bucket.encryption_key.grant_encrypt_decrypt(glue_job_role)
        self.output_bucket.encryption_key.grant_encrypt_decrypt(glue_job_role)

        # This bucket prefix is used for operation of the glue job in table partitioning
        # Object do not need to be stored and can be removed
        self.artifacts_bucket.add_lifecycle_rule(
            expiration=Duration.days(globals.GLUE_ATHENA_OUTPUT_LIFECYCLE_DAYS),
            prefix="athena",
        )

        # Create the metrics etl glue job
        glue_job = glue.CfnJob(
            self,
            "Job",
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{self.artifacts_bucket.bucket_name}/glue/{self.file_name}",
            ),
            glue_version="4.0",
            role=glue_job_role.role_arn,
            default_arguments={
                "--SOURCE_BUCKET": self.source_bucket.bucket_name,
                "--OUTPUT_BUCKET": self.output_bucket.bucket_name,
                "--DATABASE_NAME": self.GLUE_DATABASE_NAME,
                "--AWS_REGION": Aws.REGION,
                "--ATHENA_QUERY_BUCKET": self.artifacts_bucket.bucket_name,
                "--enable-continuous-cloudwatch-log": "true",
                "--enable-metrics": "true",
                "--enable-observability-metrics": "true",
            },
            name=self.GLUE_JOB_NAME,
            execution_property=glue.CfnJob.ExecutionPropertyProperty(
                max_concurrent_runs=globals.GLUE_MAX_CONCURRENT_RUNS
            ),
            timeout=globals.GLUE_TIMEOUT_MINS,
        )

        return glue_job

    def _create_glue_job_trigger(self) -> SolutionsPythonFunction:
        """
        This function creates a Lambda function to trigger the Glue Job when DataSync completes a file transfer task for metrics
        """
        # Create metrics etl lambda for triggering the glue job
        lambda_function = SolutionsPythonFunction(
            self,
            "TriggerFunction",
            Path(__file__).absolute().parents[0]
            / "glue_trigger_lambda"
            / "start_glue_job.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            description="Lambda function for triggering metrics Glue Etl",
            memory_size=256,
            timeout=Duration.minutes(5),
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                self.powertools_layer,
                SolutionsLayer.get_or_create(self),
                self.metrics_layer,
            ],
            environment={
                "SOLUTION_ID": self.node.try_get_context("SOLUTION_ID"),
                "SOLUTION_VERSION": self.node.try_get_context("SOLUTION_VERSION"),
                "GLUE_JOB_NAME": self.GLUE_JOB_NAME,
                "RESOURCE_PREFIX": Aws.STACK_NAME,
                "METRICS_NAMESPACE": self.node.try_get_context("METRICS_NAMESPACE"),
                "DATASYNC_REPORT_BUCKET": self.artifacts_bucket.bucket_name,
                "AWS_ACCOUNT_ID": Aws.ACCOUNT_ID,
            },
        )

        # Create metrics etl lambda iam policy permissions
        lambda_policy = iam.Policy(
            self,
            "LambdaPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "cloudwatch:PutMetricData",
                    ],
                    resources=[
                        "*"  # NOSONAR
                    ],
                    conditions={
                        "StringEquals": {
                            "cloudwatch:namespace": self.node.try_get_context(
                                "METRICS_NAMESPACE"
                            )
                        }
                    },
                ),
                iam.PolicyStatement(
                    actions=[
                        "glue:StartJobRun",
                    ],
                    resources=[
                        f"arn:aws:glue:{Aws.REGION}:{Aws.ACCOUNT_ID}:job/{self.GLUE_RESOURCE_PREFIX}-job"
                    ],
                ),
                iam.PolicyStatement(
                    actions=self.S3_READ_ACTIONS,
                    resources=[
                        self.artifacts_bucket.bucket_arn,
                        f"{self.artifacts_bucket.bucket_arn}/*",
                    ],
                    conditions=self.S3_CONDITIONS,
                ),
            ],
        )
        lambda_function.role.attach_inline_policy(lambda_policy)
        self.artifacts_bucket.encryption_key.grant_encrypt_decrypt(lambda_function.role)

        # Create eventbridge rule to trigger metrics etl lambda on successful datasync executions of metrics
        lambda_function.add_permission(
            id="InvokeLambda",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            action="lambda:InvokeFunction",
        )
        rule = events.Rule(
            self,
            "EventBridgeRule",
            event_pattern=events.EventPattern(
                source=["aws.datasync"],
                detail_type=["DataSync Task Execution State Change"],
                resources=[
                    ""
                ],  # due to a cdk limitation, this is left empty and replaced with the override below (https://github.com/aws/aws-cdk/issues/28462)
                detail={"State": ["SUCCESS"]},
            ),
        )
        rule.node.default_child.add_property_override(
            "EventPattern.resources",
            [{"wildcard": f"{self.datasync_task.attr_task_arn}/execution/*"}],
        )
        rule.node.add_dependency(self.datasync_task)
        rule.add_target(targets.LambdaFunction(lambda_function))

        return lambda_function
