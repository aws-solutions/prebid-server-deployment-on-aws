# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk as cdk
from aws_cdk import Aws
from aws_cdk import (
    aws_cloudtrail as cloud_trail,
    aws_iam as iam,
    aws_kms as kms,
    aws_s3 as s3,
)
from constructs import Construct


class CloudTrailConstruct(Construct):
    def __init__(
        self,
        scope,
        id,
        s3_buckets,
    ) -> None:
        """
        This construct creates a CloudTrail resource and sets S3 and Lambda Data Events.
        """
        super().__init__(scope, id)

        self.s3_buckets = s3_buckets
        self.logging_bucket = self._create_logging_bucket()

        self.trail = cloud_trail.Trail(
            self,
            "S3AndLambdaTrail",
            bucket=self.logging_bucket,
            is_multi_region_trail=False,
            include_global_service_events=False,
            management_events=cloud_trail.ReadWriteType.ALL,
        )

        self.trail.add_s3_event_selector(
            [cloud_trail.S3EventSelector(bucket=bucket) for bucket in self.s3_buckets]
        )

        self.trail.node.add_dependency(self.logging_bucket)

    def _create_logging_bucket(self) -> s3.Bucket:
        logging_bucket_key = kms.Key(
            self,
            id="CloudtrailLoggingBucketKey",
            description="Cloudtrail Logging Bucket Key",
            enable_key_rotation=True,
            pending_window=cdk.Duration.days(30),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        kms_bucket_policy = iam.PolicyStatement(
            sid="Allow access to CloudTrailLoggingBucketKey",
            principals=[
                iam.ServicePrincipal("cloudtrail.amazonaws.com"),
                iam.ServicePrincipal("delivery.logs.amazonaws.com"),
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
        logging_bucket_key.add_to_resource_policy(kms_bucket_policy)

        logging_bucket = s3.Bucket(
            self,
            id="CloudTrailLoggingBucket",
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
            access_control=s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption_key=logging_bucket_key,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            versioned=True,
            enforce_ssl=True,
            object_lock_enabled=True,
            server_access_logs_prefix="access-logs/"
        )
        logging_bucket.node.add_dependency(logging_bucket_key)
        enable_s3_access_logs_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[
                iam.ServicePrincipal("logging.s3.amazonaws.com")
            ],
            actions=["s3:PutObject"],
            resources=[
                f"{logging_bucket.bucket_arn}/access-logs/*"
            ]
        )
        logging_bucket.add_to_resource_policy(
            enable_s3_access_logs_statement
        )

        return logging_bucket
