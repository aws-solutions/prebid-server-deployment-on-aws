## Prerequisites

- [Python 3.9](https://www.python.org/downloads/)
- [AWS CDK](https://aws.amazon.com/cdk/) version 2.45.0 or higher

## Build the solution for deployment
You can use the AWS CDK to deploy the solution directly or use the CloudFormation template described in downstream sections.  
[Bootstrapping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) configurations.

```shell script
# Installing the Python dependencies and setting up CDK 

cd <repository_name> 

# Create python virtualenv and activate it 
.venv python -m venv .venv
source .venv/bin/activate

# Install required python packages 
pip install -r source/requirements-dev.txt

# change into the infrastructure directory
cd source/infrastructure

# set environment variables required by the solution - use your own bucket name here
export BUCKET_NAME="placeholder"

# bootstrap CDK (required once - deploys a CDK bootstrap CloudFormation stack for assets)  
cdk bootstrap --cloudformation-execution-policies arn:aws:iam::aws:policy/<PolicyName>

# deploy with CDK
cdk deploy
```

At this point, the stack will be built and deployed using CDK - the template will take on default CloudFormation
parameter values. To modify the stack parameters, you can use the `--parameters` flag in CDK deploy - for example:

```shell script
cdk deploy --parameters [...] 
```

## Package the solution for release 

It is highly recommended to use CDK to deploy this solution (see step #1 above). While CDK is used to develop the
solution, to package the solution for release as a CloudFormation template use the `build-s3-cdk-dist` script:

```
cd <repository_name>/deployment

export DIST_OUTPUT_BUCKET=my-bucket-name
export SOLUTION_NAME=my-solution-name
export VERSION=my-version

build-s3-cdk-dist deploy \
    --source-bucket-name $DIST_OUTPUT_BUCKET \
    --solution-name $SOLUTION_NAME \
    --version-code $VERSION \
    --cdk-app-path ../source/infrastructure/deploy.py \
    --cdk-app-entrypoint  app:build_app --sync 
```

> **Note**: `build-s3-cdk-dist` will use your current configured `AWS_REGION` and `AWS_PROFILE`. To set your defaults
install the [AWS Command Line Interface](https://aws.amazon.com/cli/) and run `aws configure`.   
Additionally, the ```--region``` flag can be passed to the build-s3-cdk-dist script to specify the AWS region.

#### Parameter Details:
 
- `$DIST_OUTPUT_BUCKET` - This is the global name of the distribution. For the bucket name, the AWS Region is added to
the global name (example: 'my-bucket-name-us-east-1') to create a regional bucket. The lambda artifact should be
uploaded to the regional buckets for the CloudFormation template to pick it up for deployment.
- `$SOLUTION_NAME` - The name of This solution (example: your-solution-name)
- `$VERSION` - The version number of the change

> **Notes**: The `build_s3_cdk_dist` script expects the bucket name as one of its parameters, and this value should 
not include the region suffix. See below on how to create the buckets expected by this solution:
> 
> The `SOLUTION_NAME`, and `VERSION` variables might also be defined in the `cdk.json` file. 

## Upload deployment assets to your Amazon S3 buckets

Create the CloudFormation bucket defined above, as well as a regional bucket in the region you wish to deploy. The
CloudFormation template is configured to pull the Lambda deployment packages from Amazon S3 bucket in the region the
template is being launched in. Create a bucket in the desired region with the region name appended to the name of the
bucket. eg: for us-east-1 create a bucket named: ```my-bucket-us-east-1```. 

For example:

```bash 
aws s3 mb s3://my-bucket-name --region us-east-1
aws s3 mb s3://my-bucket-name-us-east-1 --region us-east-1
```

Copy the built S3 assets to your S3 buckets: 

```
use the --sync option of build-s3-cdk-dist to upload the global and regional assets
```

> **Notes**: Choose your desired region by changing region in the above example from us-east-1 to your desired region 
of the S3 buckets.

## Launch the CloudFormation template

* Get the link of `your-solution-name.template` uploaded to your Amazon S3 bucket.
* Deploy the solution to your account by launching a new AWS CloudFormation stack using the link of the 
`your-solution-name.template`.
  
***

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

SPDX-License-Identifier: Apache-2.0