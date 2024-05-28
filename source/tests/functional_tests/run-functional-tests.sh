#!/bin/bash
###############################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
###############################################################################

set -exuo pipefail

usage() {
  msg "$msg"
  cat <<EOF
Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [--in-venv] [--test-file-name] [--extras] [--region] --profile PROFILE --stack-name STACK_NAME

Available options:

-h, --help        Print this help and exit (optional)
-v, --verbose     Print script debug info (optional)
--in-venv         Run test in an existing virtual environment [--in-venv 1] (optional)
--extras          Append more commands to pytest run (optional)
--stack-name      Name of the Cloudformation stack where the solution is running
--profile         AWS profile for CLI commands
--region          AWS region for CLI commands (optional, default to us-east-1)
--test-file-name  Run individual test file (optional) e.g --test-file-name test_bad_requests.py

EOF
  exit 1
}

msg() {
  echo >&2 -e "${1-}"
}

parse_params() {
  # default values of variables set from params
  flag=0
  param=''

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    --in-venv)
      in_venv="${2}"
      shift
      ;;
    --extras)
      extras="${2}"
      shift
      ;;
    --stack-name)
      stack_name="${2}"
      shift
      ;;
    --profile)
      profile="${2}"
      shift
      ;;
    --region)
      region="${2}"
      shift
      ;;
    --test-file-name)
      TEST_FILE_NAME="${2}" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${profile}" ]] && usage "Missing required parameter: profile"
  [[ -z "${stack-name}" ]] && usage "Missing required parameter: stack-name"

  return 0
}

parse_params "$@"

default_region=${region:-"us-east-1"}

msg "Parameters:"
msg "- Stack name: ${stack_name}"
msg "- Profile: ${profile}"
msg "- Region: ${default_region}"

# Get reference for all important folders
current_dir="$PWD"
source_dir="$(
  cd $current_dir/../../../source
  pwd -P
)"

echo "------------------------------------------------------------------------------"
echo "Creating a temporary Python virtualenv for this script"
echo "------------------------------------------------------------------------------"
# Make sure aws cli is installed
if [[ ! -x "$(command -v aws)" ]]; then
  echo "ERROR: This script requires the AWS CLI to be installed. Please install it then run again."
  exit 1
fi

create_venv() {
  if [[ ${in_venv:-0} -ne 1 ]]; then
    echo "Create virtual python environment:"
    VENV=$(mktemp -d) && echo "$VENV"
    command -v python3 >/dev/null
    if [ $? -ne 0 ]; then
      echo "ERROR: install Python3 before running this script"
      exit 1
    fi
    python3 -m venv "$VENV"
    source "$VENV"/bin/activate
    pip3 install wheel
    pip3 install --quiet -r requirements-test.txt
  else
    echo "Run tests in a virtualenv, skip creating virtualenv"
  fi
}

create_venv


#################################
####   TEST Prebid Server   #####
#################################
echo "Test Prebid Server"

cd $current_dir

export CLOUDFRONT_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $stack_name --query "Stacks[].Outputs[?OutputKey=='PrebidCloudFrontDistributionEndpoint'].OutputValue" --output text --profile $profile --region $default_region)

TEST_FILE_NAME=./${TEST_FILE_NAME-}

pytest $TEST_FILE_NAME -vv -s -W ignore::DeprecationWarning -p no:cacheproviders ${extras-}

if [[ ${in_venv:-0} -ne 1 ]]; then
  echo "Deactivate virtualenv"
  deactivate
else
  echo "Run tests in virtualenv, no deactivate"
fi

echo "End of all tests"
exit 0