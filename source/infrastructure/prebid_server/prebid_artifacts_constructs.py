# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


from aws_cdk import Aws, RemovalPolicy, CustomResource
from aws_cdk import aws_iam as iam, aws_lambda, aws_s3 as s3, aws_kms as kms, Duration

from constructs import Construct
from aws_lambda_layers.aws_solutions.layer import SolutionsLayer
from aws_solutions.cdk.aws_lambda.layers.aws_lambda_powertools import PowertoolsLayer
from aws_solutions.cdk.aws_lambda.python.function import SolutionsPythonFunction
import prebid_server.stack_constants as globals


class ArtifactsManager(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.bucket = self.create_artifact_bucket()
        self.upload_artifacts_function = self.create_custom_resource_lambda()
        self.custom_resource = self.create_custom_resource(
            service_token_function=self.upload_artifacts_function
        )

    def create_artifact_bucket(self) -> s3.Bucket:
        artifact_bucket_key = kms.Key(
            self,
            id="BucketKey",
            description="Artifact Bucket Key",
            enable_key_rotation=True,
            pending_window=Duration.days(30),
            removal_policy=RemovalPolicy.DESTROY,
        )
        kms_bucket_policy = iam.PolicyStatement(
            sid="Allow access to ArtifactBucket",
            principals=[
                iam.ServicePrincipal("s3.amazonaws.com"),
                iam.ServicePrincipal("lambda.amazonaws.com"),
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
                    "aws:SourceAccount": [Aws.ACCOUNT_ID],
                }
            },
        )
        artifact_bucket_key.add_to_resource_policy(kms_bucket_policy)
        # This bucket is used as temporary storage of Glue ETL script, Athena query outputs, and DataSync reports. This bucket is not used to store customer data.
        bucket = s3.Bucket(
            self,
            id="Bucket",
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
            access_control=s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption_key=artifact_bucket_key,
            removal_policy=RemovalPolicy.DESTROY,
            versioned=False,  # NOSONAR
            auto_delete_objects=True,
            enforce_ssl=True,
        )
        bucket.node.add_dependency(artifact_bucket_key)
        return bucket

    def create_custom_resource_lambda(self) -> SolutionsPythonFunction:
        custom_resource_role = iam.Role(
            self,
            "CrRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "LambdaCrLoggingPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            resources=[
                                f"arn:{Aws.PARTITION}:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/*"
                            ],
                        )
                    ]
                ),
                "LambdaCrS3Policy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3:DeleteObject",
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:ListBucket",
                            ],
                            resources=[
                                self.bucket.bucket_arn,
                                f"{self.bucket.bucket_arn}/*",
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceAccount": [Aws.ACCOUNT_ID]
                                }
                            },
                        )
                    ]
                ),
            },
        )
        custom_resource_role.node.add_dependency(self.bucket)
        self.bucket.encryption_key.grant_encrypt_decrypt(custom_resource_role)

        upload_artifacts_function = SolutionsPythonFunction(
            self,
            "CrFunction",
            globals.CUSTOM_RESOURCES_PATH
            / "artifacts_bucket_lambda"
            / "upload_files.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            role=custom_resource_role,
            description="Lambda function for uploading Solution artifacts to S3",
            memory_size=256,
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                PowertoolsLayer.get_or_create(self),
                SolutionsLayer.get_or_create(self),
            ],
            environment={
                "SOLUTION_ID": self.node.try_get_context("SOLUTION_ID"),
                "SOLUTION_VERSION": self.node.try_get_context("SOLUTION_VERSION"),
            },
        )

        return upload_artifacts_function

    def create_custom_resource(self, service_token_function) -> CustomResource:
        custom_resource = CustomResource(
            self,
            f"Upload{id}Cr",
            service_token=service_token_function.function_arn,
            properties={
                "artifacts_bucket_name": self.bucket.bucket_name,
            },
        )
        custom_resource.node.add_dependency(self.upload_artifacts_function)

        return custom_resource
