# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import jsii
import aws_cdk
from aws_cdk import Aws
from aws_cdk import aws_servicecatalogappregistry as appregistry
from constructs import Construct, IConstruct


@jsii.implements(aws_cdk.IAspect)
class AppRegistry(Construct):
    """This construct creates the resources required for AppRegistry and injects them as Aspects"""

    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)
        self.solution_name = scope.node.try_get_context("SOLUTION_NAME")
        self.solution_id = scope.node.try_get_context("SOLUTION_ID")
        self.solution_version = scope.node.try_get_context("SOLUTION_VERSION")
        self.application_type = "AWS-Solutions"
        self._application = {}
        self._attribute_group = {}
        self._attribute_group_association = {}
        self._application_resource_association = {}

    def visit(self, node: IConstruct) -> None:
        if isinstance(node, aws_cdk.Stack):
            application = self.__get_or_create_application(node)
            attribute_group = self.__get_or_create_attribute_group(node)
            self.__get_or_create_attribute_group_association(
                node, application, attribute_group
            )
            self.__get_or_create_application_resource_association(node, application)

    def __get_or_create_application(
        self, stack: aws_cdk.Stack
    ) -> appregistry.CfnApplication:
        if stack.stack_name not in self._application:
            self._application[stack.stack_name] = appregistry.CfnApplication(
                stack,
                "AppRegistryApp",
                name=f"App-{Aws.STACK_NAME}",
                description=f"Service Catalog application to track and manage all your resources for the solution {self.solution_name}",
                tags={
                    "Solutions:SolutionID": self.solution_id,
                    "Solutions:SolutionName": self.solution_name,
                    "Solutions:SolutionVersion": self.solution_version,
                    "Solutions:ApplicationType": self.application_type,
                },
            )

        return self._application[stack.stack_name]

    def __get_or_create_attribute_group(
        self, stack: aws_cdk.Stack
    ) -> appregistry.CfnAttributeGroup:
        if stack.stack_name not in self._attribute_group:
            self._attribute_group[stack.stack_name] = appregistry.CfnAttributeGroup(
                stack,
                "AppAttributeGroup",
                name=f"AttrGrp-{Aws.STACK_NAME}",
                description=f"Attribute group for solution information of {self.solution_name}",
                attributes={
                    "version": self.solution_version,
                    "solutionID": self.solution_id,
                    "solutionName": self.solution_name,
                    "applicationType": self.application_type,
                },
            )
        return self._attribute_group[stack.stack_name]

    def __get_or_create_attribute_group_association(
        self,
        stack: aws_cdk.Stack,
        application: appregistry.CfnApplication,
        attribute_group: appregistry.CfnAttributeGroup,
    ) -> appregistry.CfnAttributeGroupAssociation:
        hash_key = (stack.stack_name, attribute_group.name)
        if hash_key not in self._attribute_group_association:
            attribute_group_association = appregistry.CfnAttributeGroupAssociation(
                stack,
                "AttributeGroupAssociation",
                application=application.name,
                attribute_group=attribute_group.name,
            )
            attribute_group_association.node.add_dependency(application)
            attribute_group_association.node.add_dependency(attribute_group)
            self._attribute_group_association[hash_key] = attribute_group_association
        return self._attribute_group_association[hash_key]

    def __get_or_create_application_resource_association(
        self, stack: aws_cdk.Stack, application: appregistry.CfnApplication
    ) -> appregistry.CfnResourceAssociation:
        if stack.stack_name not in self._application_resource_association:
            cfn_resource_association = appregistry.CfnResourceAssociation(
                stack,
                "AppResourceAssociation",
                application=application.name,
                resource=Aws.STACK_ID,
                resource_type="CFN_STACK",
            )
            cfn_resource_association.node.add_dependency(application)
            self._application_resource_association[stack.stack_name] = (
                cfn_resource_association
            )
        return self._application_resource_association[stack.stack_name]
