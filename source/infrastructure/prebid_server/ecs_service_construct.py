# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from aws_cdk import Duration
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from constructs import Construct

import prebid_server.stack_constants as globals


class ECSServiceConstruct(Construct):
    def __init__(
            self,
            scope,
            id,
            prebid_vpc,
            prebid_cluster,
            prebid_task_definition,
            prebid_task_subnets,
            prebid_container,
            prebid_fs,
    ) -> None:
        """
        This construct creates EFS resources.
        """
        super().__init__(scope, id)

        fargate_service = ecs.FargateService(
            self,
            "PrebidFargateService",
            cluster=prebid_cluster,
            task_definition=prebid_task_definition,
            vpc_subnets=ec2.SubnetSelection(subnets=prebid_task_subnets),
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE",
                    weight=globals.FARGATE_RESERVED_WEIGHT,
                ),
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE_SPOT",
                    weight=globals.FARGATE_SPOT_WEIGHT,
                ),
            ],
        )

        self.alb_target_group = elbv2.ApplicationTargetGroup(
            self,
            "ALBTargetGroup",
            port=80, targets=[fargate_service.load_balancer_target(
                container_name=prebid_container.container_name,
                container_port=prebid_container.container_port)],
            vpc=prebid_vpc,
        )

        # Suppress cfn_guard warning about open egress in the Fargate service security group because Prebid Server containers require open egress in order to connect to demand partners.
        fargate_service_security_group = fargate_service.connections.security_groups[0]
        security_group_l1_construct = fargate_service_security_group.node.find_child(id='Resource')
        security_group_l1_construct.add_metadata("guard", {
            'SuppressedRules': ['EC2_SECURITY_GROUP_EGRESS_OPEN_TO_WORLD_RULE',
                                'SECURITY_GROUP_EGRESS_ALL_PROTOCOLS_RULE']})

        # Allow traffic to/from EFS
        fargate_service.connections.allow_from(
            prebid_fs, ec2.Port.tcp(globals.EFS_PORT)
        )
        fargate_service.connections.allow_to(
            prebid_fs, ec2.Port.tcp(globals.EFS_PORT)
        )

        # Add health check
        self.alb_target_group.configure_health_check(
            path=globals.HEALTH_PATH,
            interval=Duration.seconds(globals.HEALTH_CHECK_INTERVAL_SECS),
            timeout=Duration.seconds(globals.HEALTH_CHECK_TIMEOUT_SECS),
        )

        self.scalable_target = fargate_service.auto_scale_task_count(
            min_capacity=globals.TASK_MIN_CAPACITY,
            max_capacity=globals.TASK_MAX_CAPACITY,
        )

        self.scalable_target.scale_on_cpu_utilization(
            "FargateServiceCpuScaling",
            target_utilization_percent=globals.CPU_TARGET_UTILIZATION_PCT,
        )

        self.scalable_target.scale_on_memory_utilization(
            "FargateServiceMemoryScaling",
            target_utilization_percent=globals.MEMORY_TARGET_UTILIZATION_PCT,
        )
