# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for prebid-server-deployment-on-aws template.
# USAGE:
#   ./run-unit-tests.sh --test-file-name test_prebid_server_template.py
###############################################################################

import pytest

import aws_cdk as cdk
from aws_solutions.cdk import CDKSolution
from aws_cdk.assertions import Template, Capture, Match

import prebid_server.stack_constants as globals


@pytest.fixture(scope="module")
def mock_solution():
     
    return CDKSolution(cdk_json_path="../source/infrastructure/cdk.json")


@pytest.fixture(scope="module")
def template(mock_solution):
    from prebid_server.prebid_server_stack import PrebidServerStack

    app = cdk.App(context=mock_solution.context.context)
    stack = PrebidServerStack(app, PrebidServerStack.name, description=PrebidServerStack.description,
                            template_filename=PrebidServerStack.template_filename,
                            synthesizer=mock_solution.synthesizer)
    yield Template.from_stack(stack)


@pytest.mark.run(order=1)
def test_prebid_server_template(template):
    mapping_solution(template)
    mapping_source_code(template)
    metrics_etl_s3_create_output_bucket(template)
    metrics_etl_job(template)
    create_glue_job_trigger(template)
    create_artifact_bucket(template)
    create_custom_resource_lambda(template)
    artifact_upload_glue_script(template)
    get_prefix_id_function_policy(template)
    waf_web_acl_function_role(template)
    waf_web_acl_cr(template)
    waf_web_acl_function_policy(template)
    del_waf_acl_function_role(template)
    delete_waf_web_acl_custom_res(template)
    prebid_vpc(template)
    prebid_vpc_nat_gateway(template)
    prebid_vpc_subnet_ec2_route(template)
    prebid_vpc_pvt_ec2_subnet(template)
    prebid_efs_security_group(template)
    prebid_efs_access_point(template)
    prebid_task_default_policy(template)
    prebid_task_definition_task_role_iam_policy(template)
    prebid_elastic_load_balancer(template)
    prebid_public_load_balancing_listener(template)
    prebid_public_load_balancing_target_group(template)
    prebid_fargate_svc_service(template)
    ecs_util_cpu_alarm(template)
    ecs_util_memory_alarm(template)
    alb5xx_error_alarm(template)
    alb4xx_error_alarm(template)
    data_sync_logs_task(template)
    data_sync_metrics_bucket_policy(template)
    efs_cleanup_vpc_custom_res(template)
    solution_metrics_anonymous_data(template)
    metrics_etl_meter_table(template)
    metrics_etl_histogram_table(template)
    metrics_etl_guage_table(template)
    metrics_etl_counter_table(template)
    metrics_etl_timer_table(template)


def mapping_solution(template):
    template.has_mapping(
        "Solution",
        {
            'Data': {
                'ID': "SO0248",
                'Version': "v1.0.1",
                'SendAnonymizedData': 'Yes'
            }
        }
    )


def mapping_source_code(template):
    template.has_mapping(
        "SourceCode",
        {
            'General': {
                'S3Bucket': "BUCKET_NAME",
                'KeyPrefix': 'Prebid Server Deployment on AWS/v1.0.1'
            }
        }
    )


def metrics_etl_s3_create_output_bucket(template):
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {
                            "KMSMasterKeyID": {
                                "Fn::GetAtt": [
                                    Match.any_value(),
                                    "Arn"
                                ]
                            },
                            "SSEAlgorithm": "aws:kms"
                        }
                    }
                ]
            }
        }
    )


def metrics_etl_job(template):
    template.has_resource_properties(
        "AWS::Glue::Job",
        {
            'Command': {
                'Name': 'glueetl',
                'PythonVersion': '3',
                'ScriptLocation': {
                    'Fn::Join': [
                        '',
                        [
                            's3://',
                            {
                                'Ref': 'ArtifactsBucket88671897'
                            },
                            '/glue/metrics_glue_script.py'
                        ]
                    ]
                }
            },
            'DefaultArguments': {
                '--SOURCE_BUCKET': {
                    'Ref': 'DataSyncMetricsBucket76641540'
                },
                '--OUTPUT_BUCKET': {
                    'Ref': 'MetricsEtlBucket69CB3729'
                },
                '--DATABASE_NAME': {
                    'Fn::Join': [
                        '',
                        [
                            {
                                'Ref': 'AWS::StackName'
                            },
                            '-',
                            {
                                'Ref': 'AWS::Region'
                            },
                            '-metricsetl-database'
                        ]
                    ]
                },
                '--AWS_REGION': {
                    'Ref': 'AWS::Region'
                },
                '--ATHENA_QUERY_BUCKET': {
                    'Ref': 'ArtifactsBucket88671897'
                },
                '--enable-continuous-cloudwatch-log': 'true',
                '--enable-metrics': 'true',
                '--enable-observability-metrics': 'true'
            },
            "ExecutionProperty": {
                "MaxConcurrentRuns": 10
            },
            'GlueVersion': '4.0',
            'Name': {
                'Fn::Join': [
                    '',
                    [
                        {
                            'Ref': 'AWS::StackName'
                        },
                        '-',
                        {
                            'Ref': 'AWS::Region'
                        },
                        '-metricsetl-job'
                    ]
                ]
            },
            'Role': {
                'Fn::GetAtt': [
                    'MetricsEtlJobRole8990170A',
                    'Arn'
                ]
            },
            'Timeout': globals.GLUE_TIMEOUT_MINS
        }
    )


def create_glue_job_trigger(template):
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "detail": {
                    "State": ["SUCCESS"],
                },
                "detail-type": [
                    "DataSync Task Execution State Change"
                ],
                "source": [
                    "aws.datasync"
                ],
                "resources": [
                    {
                        "wildcard": {
                            "Fn::Join": [
                                "",
                                [
                                    {
                                        "Fn::GetAtt": [
                                            "DataSyncMetricsTask932C2D80",
                                            "TaskArn"
                                        ]
                                    },
                                    "/execution/*"
                                ]
                            ]
                        }
                    }
                ]
            },
            "State": "ENABLED",
            "Targets": [
                {
                    "Arn": {
                        "Fn::GetAtt": [
                            "MetricsEtlTriggerFunction098DA476",
                            "Arn"
                        ]
                    },
                    "Id": "Target0"
                }
            ]
        }
    )


def create_artifact_bucket(template):
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "AccessControl": "BucketOwnerFullControl",
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {
                            "KMSMasterKeyID": {},
                            "SSEAlgorithm": "aws:kms"
                        }
                    }
                ]
            },
            "LifecycleConfiguration": {
                "Rules": [
                    {
                        "ExpirationInDays": 1,
                        "Prefix": "datasync",
                        "Status": "Enabled"
                    },
                    {
                        "ExpirationInDays": 1,
                        "Prefix": "athena",
                        "Status": "Enabled"
                    }
                ]
            },
            "OwnershipControls": {
                "Rules": [
                    {
                        "ObjectOwnership": "ObjectWriter"
                    }
                ]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True
            },
            "Tags": [
                {
                    "Key": "aws-cdk:auto-delete-objects",
                    "Value": "true"
                }
            ]
        }
    )


def create_custom_resource_lambda(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": [
                    {
                        "Action": [
                            "kms:Decrypt",
                            "kms:Encrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*"
                        ],
                        "Effect": "Allow",
                        "Resource": {
                            "Fn::GetAtt": [
                                "ArtifactsBucketKeyD2E238BB",
                                "Arn"
                            ]
                        }
                    }
                ],
            }
        }
    )


def artifact_upload_glue_script(template):
    template.has_resource_properties(
        "AWS::CloudFormation::CustomResource",
        {
            'ServiceToken': {
                'Fn::GetAtt': [
                    'ArtifactsCrFunction29141FFE',
                    'Arn'
                ]
            },
            'artifacts_bucket_name': {
                'Ref': 'ArtifactsBucket88671897'
            }
        }
    )


def get_prefix_id_function_policy(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            'PolicyDocument': {
                'Statement': [
                    {
                        'Action': 'ec2:DescribeManagedPrefixLists',
                        'Effect': 'Allow',
                        'Resource': '*'
                    }
                ],
                'Version': '2012-10-17'
            },
            'PolicyName': 'GetPrefixIdFunctionPolicyE931DEE0',
            'Roles': [
                {
                    'Ref': 'GetPrefixIdFunctionRole29EE98C6'
                }
            ]
        }
    )


def waf_web_acl_function_role(template):
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            'AssumeRolePolicyDocument': {
                'Statement': [
                    {
                        'Action': 'sts:AssumeRole',
                        'Effect': 'Allow',
                        'Principal': {
                            'Service': 'lambda.amazonaws.com'
                        }
                    }
                ],
                'Version': '2012-10-17'
            },
            'Policies': [
                {
                    'PolicyDocument': {
                        'Statement': [
                            {
                                'Action': [
                                    'logs:CreateLogGroup',
                                    'logs:CreateLogStream',
                                    'logs:PutLogEvents'
                                ],
                                'Effect': 'Allow',
                                'Resource': {
                                    'Fn::Join': [
                                        '',
                                        [
                                            'arn:',
                                            {
                                                'Ref': 'AWS::Partition'
                                            },
                                            ':logs:',
                                            {
                                                'Ref': 'AWS::Region'
                                            },
                                            ':',
                                            {
                                                'Ref': 'AWS::AccountId'
                                            },
                                            ':log-group:/aws/lambda/*'
                                        ]
                                    ]
                                }
                            }
                        ],
                        'Version': '2012-10-17'
                    },
                    'PolicyName': 'LambdaFunctionServiceRolePolicy'
                }
            ]
        }
    )


def waf_web_acl_cr(template):
    template.has_resource_properties(
        "AWS::CloudFormation::CustomResource", {
            'ServiceToken': {
                'Fn::GetAtt': [
                    'CreateWafWebAclFunctionA6AF6419',
                    'Arn'
                ]
            }
        }
    )


def waf_web_acl_function_policy(template):
    template.has_resource_properties(
        "AWS::IAM::Policy", {
            'PolicyDocument': {
                'Statement': [
                    {
                        'Action': [
                            'cloudfront:GetDistribution',
                            'cloudfront:GetDistributionConfig',
                            'cloudfront:ListDistributions',
                            'cloudfront:ListDistributionsByWebACLId',
                            'cloudfront:UpdateDistribution'
                        ],
                        'Effect': 'Allow',
                        'Resource': {
                            'Fn::Join': [
                                '',
                                [
                                    'arn:aws:cloudfront::',
                                    {
                                        'Ref': 'AWS::AccountId'
                                    },
                                    ':distribution/',
                                    {
                                        'Ref': 'PrebidCloudFrontDist4A157CA2'
                                    }
                                ]
                            ]
                        }
                    },
                    {
                        'Action': [
                            'cloudwatch:ListMetrics',
                            'cloudwatch:GetMetricStatistics',
                            'ec2:DescribeRegions'
                        ],
                        'Effect': 'Allow',
                        'Resource': '*'
                    }
                ],
                'Version': '2012-10-17'
            },
            'PolicyName': 'WafWebAclFunctionCloudFrontPolicyD66D3EFF',
            'Roles': [
                {
                    'Ref': 'CreateWafWebAclFunctionRoleC72F5770'
                },
                {
                    'Ref': 'DelWafWebAclFunctionRole780EE078'
                }
            ]
        }
    )


def del_waf_acl_function_role(template):
    template.has_resource_properties("AWS::IAM::Role", {
        'AssumeRolePolicyDocument': {
            'Statement': [
                {
                    'Action': 'sts:AssumeRole',
                    'Effect': 'Allow',
                    'Principal': {
                        'Service': 'lambda.amazonaws.com'
                    }
                }
            ],
            'Version': '2012-10-17'
        },
        'Policies': [
            {
                'PolicyDocument': {
                    'Statement': [
                        {
                            'Action': [
                                'logs:CreateLogGroup',
                                'logs:CreateLogStream',
                                'logs:PutLogEvents'
                            ],
                            'Effect': 'Allow',
                            'Resource': {
                                'Fn::Join': [
                                    '',
                                    [
                                        'arn:',
                                        {
                                            'Ref': 'AWS::Partition'
                                        },
                                        ':logs:',
                                        {
                                            'Ref': 'AWS::Region'
                                        },
                                        ':',
                                        {
                                            'Ref': 'AWS::AccountId'
                                        },
                                        ':log-group:/aws/lambda/*'
                                    ]
                                ]
                            }
                        }
                    ],
                    'Version': '2012-10-17'
                },
                'PolicyName': 'LambdaFunctionServiceRolePolicy'
            }
        ]
    })


def delete_waf_web_acl_custom_res(template):
    template.has_resource_properties("AWS::CloudFormation::CustomResource", {
        'ServiceToken': {
            'Fn::GetAtt': [
                'DelWafWebAclFunction0DA7C9FD',
                'Arn'
            ]
        },
        'CF_DISTRIBUTION_ID': {
            'Ref': 'PrebidCloudFrontDist4A157CA2'
        },
        'WAF_WEBACL_NAME': {
            'Fn::GetAtt': [
                'WafWebAclCr',
                'webacl_name'
            ]
        },
        'WAF_WEBACL_ID': {
            'Fn::GetAtt': [
                'WafWebAclCr',
                'webacl_id'
            ]
        },
        'WAF_WEBACL_LOCKTOKEN': {
            'Fn::GetAtt': [
                'WafWebAclCr',
                'webacl_locktoken'
            ]
        }
    })


def prebid_vpc(template):
    template.has_resource_properties(
        "AWS::EC2::VPC", {
            'CidrBlock': '10.8.0.0/16',
            'EnableDnsHostnames': True,
            'EnableDnsSupport': True,
            'InstanceTenancy': 'default',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': 'prebid-server-deployment-on-aws/PrebidVpc'
                }
            ]
        }
    )


def prebid_vpc_nat_gateway(template):
    template.has_resource_properties(
        "AWS::EC2::NatGateway", {
            'AllocationId': {
                'Fn::GetAtt': [
                    'PrebidVpcPrebidPublicSubnet1EIP6ED088A6',
                    'AllocationId'
                ]
            },
            'SubnetId': {
                'Ref': 'PrebidVpcPrebidPublicSubnet1Subnet9285BD8C'
            },
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': 'prebid-server-deployment-on-aws/PrebidVpc/Prebid-PublicSubnet1'
                }
            ]
        }
    )


def prebid_vpc_subnet_ec2_route(template):
    template.has_resource_properties(
        "AWS::EC2::Route", {
            'DestinationCidrBlock': '0.0.0.0/0',
            'GatewayId': {
                'Ref': 'PrebidVpcIGWF477140F'
            },
            'RouteTableId': {
                'Ref': 'PrebidVpcPrebidPublicSubnet1RouteTable5CADA5E6'
            }
        }
    )


def prebid_vpc_pvt_ec2_subnet(template):
    template.has_resource_properties(
        "AWS::EC2::Subnet", {
            'AvailabilityZone': {
                'Fn::Select': [
                    0,
                    {
                        'Fn::GetAZs': ''
                    }
                ]
            },
            'CidrBlock': '10.8.32.0/20',
            'MapPublicIpOnLaunch': False,
            'Tags': [
                {
                    'Key': 'aws-cdk:subnet-name',
                    'Value': 'Prebid-Private'
                },
                {
                    'Key': 'aws-cdk:subnet-type',
                    'Value': 'Private'
                },
                {
                    'Key': 'Name',
                    'Value': 'prebid-server-deployment-on-aws/PrebidVpc/Prebid-PrivateSubnet1'
                }
            ],
            'VpcId': {
                'Ref': 'PrebidVpcD4BD0EC9'
            }
        }
    )


def prebid_efs_security_group(template):
    template.has_resource_properties(
        "AWS::EC2::SecurityGroup", {
            'GroupDescription': 'prebid-server-deployment-on-aws/Prebid-fs/EfsSecurityGroup',
            'SecurityGroupEgress': [
                {
                    'CidrIp': '0.0.0.0/0',
                    'Description': 'Allow all outbound traffic by default',
                    'IpProtocol': '-1'
                }
            ],
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': 'prebid-server-deployment-on-aws/Prebid-fs'
                }
            ],
            'VpcId': {
                'Ref': 'PrebidVpcD4BD0EC9'
            }
        }
    )


def prebid_efs_access_point(template):
    template.has_resource_properties(
        "AWS::EFS::AccessPoint", {
            'AccessPointTags': [
                {
                    'Key': 'Name',
                    'Value': 'prebid-server-deployment-on-aws/Prebid-fs-access-point'
                }
            ],
            'FileSystemId': {
                'Ref': 'Prebidfs001EB6C9'
            },
            'PosixUser': {
                'Gid': '1001',
                'Uid': '1001'
            },
            'RootDirectory': {
                'CreationInfo': {
                    'OwnerGid': '1001',
                    'OwnerUid': '1001',
                    'Permissions': '770'
                },
                'Path': '/logging'
            }
        }
    )


def prebid_task_default_policy(template):
    template.has_resource_properties(
        "AWS::IAM::Policy", {
            'PolicyDocument': {
                'Statement': [
                    {
                        'Action': [
                            'ecr-public:GetAuthorizationToken',
                            'sts:GetServiceBearerToken',
                            'ecr-public:BatchCheckLayerAvailability',
                            'ecr-public:GetRepositoryPolicy',
                            'ecr-public:DescribeRepositories',
                            'ecr-public:DescribeRegistries',
                            'ecr-public:DescribeImages',
                            'ecr-public:DescribeImageTags',
                            'ecr-public:GetRepositoryCatalogData',
                            'ecr-public:GetRegistryCatalogData'
                        ],
                        'Effect': 'Allow',
                        'Resource': '*'
                    },
                    {
                        'Action': [
                            'elasticfilesystem:ClientRootAccess',
                            'elasticfilesystem:ClientWrite',
                            'elasticfilesystem:ClientMount',
                            'elasticfilesystem:DescribeMountTargets'
                        ],
                        'Effect': 'Allow',
                        'Resource': {
                            'Fn::Join': [
                                '',
                                [
                                    'arn:aws:elasticfilesystem:',
                                    {
                                        'Ref': 'AWS::Region'
                                    },
                                    ':',
                                    {
                                        'Ref': 'AWS::AccountId'
                                    },
                                    ':file-system/',
                                    {
                                        'Ref': 'Prebidfs001EB6C9'
                                    }
                                ]
                            ]
                        }
                    },
                    {
                        'Action': 'ec2:DescribeAvailabilityZones',
                        'Effect': 'Allow',
                        'Resource': '*'
                    }
                ],
                'Version': '2012-10-17'
            },
            'PolicyName': 'PrebidTaskDefTaskRoleDefaultPolicy79CC0930',
            'Roles': [
                {
                    'Ref': 'PrebidTaskDefTaskRole4037D1B0'
                }
            ]
        }
    )


def prebid_task_definition_task_role_iam_policy(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            'PolicyDocument': {
                'Statement': [
                    {
                        "Action": [
                            "ecr-public:GetAuthorizationToken",
                            "sts:GetServiceBearerToken",
                            "ecr-public:BatchCheckLayerAvailability",
                            "ecr-public:GetRepositoryPolicy",
                            "ecr-public:DescribeRepositories",
                            "ecr-public:DescribeRegistries",
                            "ecr-public:DescribeImages",
                            "ecr-public:DescribeImageTags",
                            "ecr-public:GetRepositoryCatalogData",
                            "ecr-public:GetRegistryCatalogData"
                        ],
                        "Effect": "Allow",
                        "Resource": "*"
                    },
                    {
                        "Action": [
                            "elasticfilesystem:ClientRootAccess",
                            "elasticfilesystem:ClientWrite",
                            "elasticfilesystem:ClientMount",
                            "elasticfilesystem:DescribeMountTargets"
                        ],
                        "Effect": "Allow",
                        "Resource": {
                            "Fn::Join": [
                                "",
                                [
                                    "arn:aws:elasticfilesystem:",
                                    {
                                        "Ref": "AWS::Region"
                                    },
                                    ":",
                                    {
                                        "Ref": "AWS::AccountId"
                                    },
                                    ":file-system/",
                                    {
                                        "Ref": "Prebidfs001EB6C9"
                                    }
                                ]
                            ]
                        }
                    },
                    {
                        "Action": "ec2:DescribeAvailabilityZones",
                        "Effect": "Allow",
                        "Resource": "*"
                    }
                ],
                'Version': '2012-10-17'
            },
            'PolicyName': 'PrebidTaskDefTaskRoleDefaultPolicy79CC0930',
            'Roles': [
                {
                    'Ref': 'PrebidTaskDefTaskRole4037D1B0'
                }
            ]
        }
    )


def prebid_elastic_load_balancer(template):
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::LoadBalancer", {
            'LoadBalancerAttributes': [
                {
                    'Key': 'deletion_protection.enabled',
                    'Value': 'false'
                }
            ],
            'Scheme': 'internet-facing',
            'SecurityGroups': [
                {
                    'Fn::GetAtt': [
                        'PrebidALBsecuritygroup6F9AE31E',
                        'GroupId'
                    ]
                }
            ],
            'Subnets': [
                {
                    'Ref': 'PrebidVpcPrebidPublicSubnet1Subnet9285BD8C'
                },
                {
                    'Ref': 'PrebidVpcPrebidPublicSubnet2SubnetC0648D3F'
                }
            ],
            'Type': 'application'
        }
    )


def prebid_public_load_balancing_listener(template):
    template.has_resource_properties("AWS::ElasticLoadBalancingV2::Listener", {
        'DefaultActions': [
            {
                'FixedResponseConfig': {
                    'ContentType': 'text/plain',
                    'MessageBody': 'Unauthorized',
                    'StatusCode': '401'
                },
                'Type': 'fixed-response'
            }
        ],
        'LoadBalancerArn': {
            'Ref': 'PrebidALBB2C5FAA5'
        },
        'Port': 80,
        'Protocol': 'HTTP'
    }
                                     )


def prebid_public_load_balancing_target_group(template):
    template.has_resource_properties("AWS::ElasticLoadBalancingV2::TargetGroup", {
        'HealthCheckIntervalSeconds': 60,
        'HealthCheckPath': '/status',
        'HealthCheckTimeoutSeconds': 5,
        'Port': 80,
        'Protocol': 'HTTP',
        'TargetGroupAttributes': [
            {
                'Key': 'stickiness.enabled',
                'Value': 'false'
            }
        ],
        'TargetType': 'ip',
        'VpcId': {
            'Ref': 'PrebidVpcD4BD0EC9'
        }
    }
                                     )


def prebid_fargate_svc_service(template):
    template.has_resource_properties(
        "AWS::ECS::Service", {
            'CapacityProviderStrategy': [
                {
                    'CapacityProvider': 'FARGATE',
                    'Weight': 1
                },
                {
                    'CapacityProvider': 'FARGATE_SPOT',
                    'Weight': 1
                }
            ],
            'Cluster': {
                'Ref': 'PrebidClusterC33B79B4'
            },
            'DeploymentConfiguration': {
                'Alarms': {
                    'AlarmNames': [

                    ],
                    'Enable': False,
                    'Rollback': False
                },
                'MaximumPercent': 200,
                'MinimumHealthyPercent': 50
            },
            'EnableECSManagedTags': False,
            'HealthCheckGracePeriodSeconds': 60,
            'LoadBalancers': [
                {
                    'ContainerName': 'Prebid-Container',
                    'ContainerPort': 8080,
                    'TargetGroupArn': {
                        'Ref': 'PrebidALBPublicListenerECSGroup33C026E6'
                    }
                }
            ],
            'NetworkConfiguration': {
                'AwsvpcConfiguration': {
                    'AssignPublicIp': 'DISABLED',
                    'SecurityGroups': [
                        {
                            'Fn::GetAtt': [
                                'PrebidFargateServiceSecurityGroupC61249EA',
                                'GroupId'
                            ]
                        }
                    ],
                    'Subnets': [
                        {
                            'Ref': 'PrebidVpcPrebidPrivateSubnet1Subnet8D5C76F3'
                        },
                        {
                            'Ref': 'PrebidVpcPrebidPrivateSubnet2SubnetF3260A7F'
                        }
                    ]
                }
            },
            'TaskDefinition': {
                'Ref': 'PrebidTaskDef8717E6A5'
            }
        })


def ecs_util_cpu_alarm(template):
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        'ActionsEnabled': False,
        'EvaluationPeriods': 1,
        'DatapointsToAlarm': 1,
        'Threshold': 72,
        'ComparisonOperator': 'GreaterThanOrEqualToThreshold',
        'TreatMissingData': 'missing',
        'Metrics': [
            {
                'Id': 'ecs_cpu_utilization',
                'Label': 'ECS CPU Utilization',
                'ReturnData': True,
                'Expression': 'SELECT AVG(CPUUtilization) FROM SCHEMA("AWS/ECS", ClusterName,ServiceName)',
                'Period': 60
            }
        ]
    })


def ecs_util_memory_alarm(template):
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        'ActionsEnabled': False,
        'EvaluationPeriods': 1,
        'DatapointsToAlarm': 1,
        'Threshold': 55,
        'ComparisonOperator': 'GreaterThanOrEqualToThreshold',
        'TreatMissingData': 'missing',
        'Metrics': [
            {
                'Id': 'ecs_memory_utilization',
                'Label': 'ECS Memory Utilization',
                'ReturnData': True,
                'Expression': 'SELECT AVG(MemoryUtilization) FROM SCHEMA("AWS/ECS", ClusterName,ServiceName)',
                'Period': 60
            }
        ]
    })


def alb5xx_error_alarm(template):
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        'ActionsEnabled': False,
        'MetricName': 'HTTPCode_ELB_5XX_Count',
        'Namespace': 'AWS/ApplicationELB',
        'Statistic': 'Average',
        'Dimensions': [
            {
                'Name': 'LoadBalancer',
                'Value': {
                    'Fn::GetAtt': [
                        'PrebidALBB2C5FAA5',
                        'LoadBalancerFullName'
                    ]
                }
            }
        ],
        'Period': 60,
        'EvaluationPeriods': 1,
        'DatapointsToAlarm': 1,
        'Threshold': 0,
        'ComparisonOperator': 'GreaterThanThreshold',
        'TreatMissingData': 'missing'
    })


def alb4xx_error_alarm(template):
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        'ActionsEnabled': False,
        'MetricName': 'HTTPCode_ELB_4XX_Count',
        'Namespace': 'AWS/ApplicationELB',
        'Statistic': 'Average',
        'Dimensions': [
            {
                'Name': 'LoadBalancer',
                'Value': {
                    'Fn::GetAtt': [
                        'PrebidALBB2C5FAA5',
                        'LoadBalancerFullName'
                    ]
                }
            }
        ],
        'Period': 60,
        'EvaluationPeriods': 1,
        'DatapointsToAlarm': 1,
        'Threshold': 1,
        'ComparisonOperator': 'GreaterThanThreshold',
        'TreatMissingData': 'missing'
    })


def data_sync_logs_task(template):
    template.has_resource_properties("AWS::DataSync::Task", {
        'DestinationLocationArn': {
            'Fn::GetAtt': [
                'DataSyncLogsS3Location8F0F3829',
                'LocationArn'
            ]
        },
        'Excludes': [
            {
                'FilterType': 'SIMPLE_PATTERN',
                'Value': '*/prebid-server.log'
            }
        ],
        'Name': {
            'Fn::Join': [
                '',
                [
                    {
                        'Ref': 'AWS::StackName'
                    },
                    '-DataSyncLogs-task'
                ]
            ]
        },
        'Options': {
            'LogLevel': 'BASIC',
            'TransferMode': 'CHANGED',
            'VerifyMode': 'ONLY_FILES_TRANSFERRED'
        },
        'Schedule': {
            'ScheduleExpression': 'cron(30 * * * ? *)'
        },
        'SourceLocationArn': {
            'Fn::GetAtt': [
                'DataSyncLogsEfsLocationC673BE45',
                'LocationArn'
            ]
        }
    })


def data_sync_metrics_bucket_policy(template):
    template.has_resource_properties("AWS::S3::BucketPolicy", {
        'Bucket': {
            'Ref': 'DataSyncMetricsBucket76641540'
        },
        'PolicyDocument': {
            'Statement': [
                {
                    'Action': [
                        "s3:GetBucketLocation",
                        "s3:ListBucketMultipartUploads",
                        "s3:AbortMultipartUpload",
                        "s3:DeleteObject",
                        "s3:ListMultipartUploadParts",
                        "s3:GetObjectTagging",
                        "s3:PutObjectTagging",
                        "s3:PutObject",
                        "s3:GetObject",
                        "s3:ListBucket"
                    ],
                    'Condition': {
                        'StringEquals': {
                            'aws:ResourceAccount': [
                                {
                                    'Ref': 'AWS::AccountId'
                                }
                            ]
                        }
                    },
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': {
                            'Fn::GetAtt': [
                                'DataSyncMetricsS3LocationRoleF3453766',
                                'Arn'
                            ]
                        }
                    },
                    'Resource': [
                        {
                            'Fn::GetAtt': [
                                'DataSyncMetricsBucket76641540',
                                'Arn'
                            ]
                        },
                        {
                            'Fn::Join': [
                                '',
                                [
                                    {
                                        'Fn::GetAtt': [
                                            'DataSyncMetricsBucket76641540',
                                            'Arn'
                                        ]
                                    },
                                    '/*'
                                ]
                            ]
                        }
                    ]
                }
            ],
            'Version': '2012-10-17'
        }
    })


def efs_cleanup_vpc_custom_res(template):
    template.has_resource_properties("AWS::CloudFormation::CustomResource", {
        'ServiceToken': {
            'Fn::GetAtt': [
                'EfsCleanupVpcEniFunction038EC712',
                'Arn'
            ]
        },
        'SECURITY_GROUP_ID': {
            'Fn::GetAtt': [
                'EfsCleanupSecurityGroupE2A1266C',
                'GroupId'
            ]
        }
    })


def solution_metrics_anonymous_data(template):
    template.has_resource_properties("Custom::AnonymousData", {
        'ServiceToken': {
            'Fn::GetAtt': [
                'MetricsMetricsFunctionD6992891',
                'Arn'
            ]
        },
        'Solution': 'Prebid Server Deployment on AWS',
        'Region': {
            'Ref': 'AWS::Region'
        }
    })


def metrics_etl_meter_table(template):
    template.has_resource_properties("AWS::Glue::Table", {
        'CatalogId': {
            'Ref': 'AWS::AccountId'
        },
        'DatabaseName': {
            'Fn::Join': [
                '',
                [
                    {
                        'Ref': 'AWS::StackName'
                    },
                    '-',
                    {
                        'Ref': 'AWS::Region'
                    },
                    '-metricsetl-database'
                ]
            ]
        },
        'TableInput': {
            'Name': 'meter',
            'PartitionKeys': [
                {
                    'Name': 'year_month',
                    'Type': 'string'
                }
            ],
            'StorageDescriptor': {
                'Columns': [
                    {
                        'Name': 'container_id',
                        'Type': 'string'
                    },
                    {
                        'Name': 'name',
                        'Type': 'string'
                    },
                    {
                        'Name': 'timestamp',
                        'Type': 'timestamp'
                    },
                    {
                        'Name': 'count',
                        'Type': 'bigint'
                    },
                    {
                        'Name': 'mean_rate',
                        'Type': 'double'
                    },
                    {
                        'Name': 'm1',
                        'Type': 'double'
                    },
                    {
                        'Name': 'm5',
                        'Type': 'double'
                    },
                    {
                        'Name': 'm15',
                        'Type': 'double'
                    },
                    {
                        'Name': 'rate_unit',
                        'Type': 'string'
                    }
                ],
                'Compressed': True,
                'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                'Location': {
                    'Fn::Join': [
                        '',
                        [
                            's3://',
                            {
                                'Ref': 'MetricsEtlBucket69CB3729'
                            },
                            '/type=meter/'
                        ]
                    ]
                },
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                'Parameters': {
                    'classification': 'parquet'
                },
                'SerdeInfo': {
                    'Name': 'ParquetHiveSerDe',
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                },
                'StoredAsSubDirectories': True
            },
            'TableType': 'EXTERNAL_TABLE'
        }
    })


def metrics_etl_histogram_table(template):
    template.has_resource_properties("AWS::Glue::Table", {
        'CatalogId': {
            'Ref': 'AWS::AccountId'
        },
        'DatabaseName': {
            'Fn::Join': [
                '',
                [
                    {
                        'Ref': 'AWS::StackName'
                    },
                    '-',
                    {
                        'Ref': 'AWS::Region'
                    },
                    '-metricsetl-database'
                ]
            ]
        },
        'TableInput': {
            'Name': 'histogram',
            'PartitionKeys': [
                {
                    'Name': 'year_month',
                    'Type': 'string'
                }
            ],
            'StorageDescriptor': {
                'Columns': [
                    {
                        'Name': 'container_id',
                        'Type': 'string'
                    },
                    {
                        'Name': 'name',
                        'Type': 'string'
                    },
                    {
                        'Name': 'timestamp',
                        'Type': 'timestamp'
                    },
                    {
                        'Name': 'count',
                        'Type': 'bigint'
                    },
                    {
                        'Name': 'min',
                        'Type': 'bigint'
                    },
                    {
                        'Name': 'max',
                        'Type': 'bigint'
                    },
                    {
                        'Name': 'mean',
                        'Type': 'double'
                    },
                    {
                        'Name': 'stddev',
                        'Type': 'double'
                    },
                    {
                        'Name': 'median',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p75',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p95',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p98',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p99',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p999',
                        'Type': 'double'
                    }
                ],
                'Compressed': True,
                'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                'Location': {
                    'Fn::Join': [
                        '',
                        [
                            's3://',
                            {
                                'Ref': 'MetricsEtlBucket69CB3729'
                            },
                            '/type=histogram/'
                        ]
                    ]
                },
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                'Parameters': {
                    'classification': 'parquet'
                },
                'SerdeInfo': {
                    'Name': 'ParquetHiveSerDe',
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                },
                'StoredAsSubDirectories': True
            },
            'TableType': 'EXTERNAL_TABLE'
        }
    })


def metrics_etl_guage_table(template):
    template.has_resource_properties("AWS::Glue::Table", {
        'CatalogId': {
            'Ref': 'AWS::AccountId'
        },
        'DatabaseName': {
            'Fn::Join': [
                '',
                [
                    {
                        'Ref': 'AWS::StackName'
                    },
                    '-',
                    {
                        'Ref': 'AWS::Region'
                    },
                    '-metricsetl-database'
                ]
            ]
        },
        'TableInput': {
            'Name': 'gauge',
            'PartitionKeys': [
                {
                    'Name': 'year_month',
                    'Type': 'string'
                }
            ],
            'StorageDescriptor': {
                'Columns': [
                    {
                        'Name': 'container_id',
                        'Type': 'string'
                    },
                    {
                        'Name': 'name',
                        'Type': 'string'
                    },
                    {
                        'Name': 'timestamp',
                        'Type': 'timestamp'
                    },
                    {
                        'Name': 'value',
                        'Type': 'string'
                    }
                ],
                'Compressed': True,
                'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                'Location': {
                    'Fn::Join': [
                        '',
                        [
                            's3://',
                            {
                                'Ref': 'MetricsEtlBucket69CB3729'
                            },
                            '/type=gauge/'
                        ]
                    ]
                },
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                'Parameters': {
                    'classification': 'parquet'
                },
                'SerdeInfo': {
                    'Name': 'ParquetHiveSerDe',
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                },
                'StoredAsSubDirectories': True
            },
            'TableType': 'EXTERNAL_TABLE'
        }
    })


def metrics_etl_counter_table(template):
    input_format_capture = Capture()
    output_format_capture = Capture()

    template.has_resource_properties("AWS::Glue::Table", {
        'CatalogId': {
            'Ref': 'AWS::AccountId'
        },
        'DatabaseName': Match.any_value(),
        'TableInput': {
            'Name': 'counter',
            'PartitionKeys': [
                {
                    'Name': 'year_month',
                    'Type': 'string'
                }
            ],
            'StorageDescriptor': {
                'Columns': [
                    {
                        'Name': 'container_id',
                        'Type': 'string'
                    },
                    {
                        'Name': 'name',
                        'Type': 'string'
                    },
                    {
                        'Name': 'timestamp',
                        'Type': 'timestamp'
                    },
                    {
                        'Name': 'count',
                        'Type': 'int'
                    }
                ],
                'Compressed': True,
                'InputFormat': input_format_capture,
                'Location': {
                    'Fn::Join': [
                        '',
                        [
                            's3://',
                            {
                                'Ref': 'MetricsEtlBucket69CB3729'
                            },
                            '/type=counter/'
                        ]
                    ]
                },
                'OutputFormat': output_format_capture,
                'Parameters': {
                    'classification': 'parquet'
                },
                'SerdeInfo': {
                    'Name': 'ParquetHiveSerDe',
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                },
                'StoredAsSubDirectories': True
            },
            'TableType': 'EXTERNAL_TABLE'
        }
    })

    assert 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat' == input_format_capture.as_string()
    assert 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat' == output_format_capture.as_string()


def metrics_etl_timer_table(template):
    input_format_capture = Capture()
    output_format_capture = Capture()
    template.has_resource_properties("AWS::Glue::Table", {
        'CatalogId': {
            'Ref': 'AWS::AccountId'
        },
        'DatabaseName': Match.any_value(),
        'TableInput': {
            'Name': 'timer',
            'PartitionKeys': [
                {
                    'Name': 'year_month',
                    'Type': 'string'
                }
            ],
            'StorageDescriptor': {
                'Columns': [
                    {
                        'Name': 'container_id',
                        'Type': 'string'
                    },
                    {
                        'Name': 'name',
                        'Type': 'string'
                    },
                    {
                        'Name': 'timestamp',
                        'Type': 'timestamp'
                    },
                    {
                        'Name': 'count',
                        'Type': 'bigint'
                    },
                    {
                        'Name': 'min',
                        'Type': 'double'
                    },
                    {
                        'Name': 'max',
                        'Type': 'double'
                    },
                    {
                        'Name': 'mean',
                        'Type': 'double'
                    },
                    {
                        'Name': 'stddev',
                        'Type': 'double'
                    },
                    {
                        'Name': 'median',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p75',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p95',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p98',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p99',
                        'Type': 'double'
                    },
                    {
                        'Name': 'p999',
                        'Type': 'double'
                    },
                    {
                        'Name': 'mean_rate',
                        'Type': 'double'
                    },
                    {
                        'Name': 'm1',
                        'Type': 'double'
                    },
                    {
                        'Name': 'm5',
                        'Type': 'double'
                    },
                    {
                        'Name': 'm15',
                        'Type': 'double'
                    },
                    {
                        'Name': 'rate_unit',
                        'Type': 'string'
                    },
                    {
                        'Name': 'duration_unit',
                        'Type': 'string'
                    }
                ],
                'Compressed': True,
                'InputFormat': input_format_capture,
                'Location': {
                    'Fn::Join': [
                        '',
                        [
                            's3://',
                            {
                                'Ref': 'MetricsEtlBucket69CB3729'
                            },
                            '/type=timer/'
                        ]
                    ]
                },
                'OutputFormat': output_format_capture,
                'Parameters': {
                    'classification': 'parquet'
                },
                'SerdeInfo': {
                    'Name': 'ParquetHiveSerDe',
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                },
                'StoredAsSubDirectories': True
            },
            'TableType': 'EXTERNAL_TABLE'
        }})

    assert 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat' == input_format_capture.as_string()
    assert 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat' == output_format_capture.as_string()
