#!/bin/bash
#
# This assumes all of the OS-level configuration has been completed and git repo has already been cloned
#
# This script should be run from the repo's deployment directory
# cd deployment
# ./build-s3-dist.sh source-bucket-base-name solution-name version-code
#
# Paramenters:
#  - source-bucket-base-name: Name for the S3 bucket location where the template will source the Lambda
#    code from. The template will append '-[region_name]' to this bucket name.
#    For example: ./build-s3-dist.sh solutions v1.0.1
#    The template will then expect the source code to be located in the solutions-[region_name] bucket
#
#  - solution-name: name of the solution for consistency
#
#  - version-code: version of the package

# set -euo pipefail

# Check to see if input has been provided:
if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    echo "Please provide the base source bucket name, trademark approved solution name and version where the lambda code will eventually reside."
    echo "For example: ./build-s3-dist.sh solutions trademarked-solution-name v1.0.1"
    exit 1
fi

SOLUTION_ID="SO0248"

# Get reference for all important folders
template_dir="$PWD"
template_dist_dir="$template_dir/global-s3-assets"
build_dist_dir="$template_dir/regional-s3-assets"
source_dir="$template_dir/../source"
cdk_out="$template_dir/cdk.out"

echo "------------------------------------------------------------------------------"
echo "[Init] Clean old dist, node_modules and bower_components folders"
echo "------------------------------------------------------------------------------"
echo "rm -rf $template_dist_dir"
rm -rf $template_dist_dir
echo "mkdir -p $template_dist_dir"
mkdir -p $template_dist_dir
echo "rm -rf $build_dist_dir"
rm -rf $build_dist_dir
echo "mkdir -p $build_dist_dir"
mkdir -p $build_dist_dir
# remove old cdk.out folder before build
rm -rf $cdk_out

# echo "------------------------------------------------------------------------------"
# echo "[Packing] Templates"
# echo "------------------------------------------------------------------------------"
# echo "cp $template_dir/*.template $template_dist_dir/"
# cp $template_dir/*.template $template_dist_dir/
# echo "copy yaml templates and rename"
# cp $template_dir/*.yaml $template_dist_dir/
# cd $template_dist_dir
# # Rename all *.yaml to *.template
# for f in *.yaml; do 
#     mv -- "$f" "${f%.yaml}.template"
# done

# cd ..
# echo "Updating code source bucket in template with $1"
# replace="s/%%SOLUTION_ID%%/$SOLUTION_ID/g"
# echo "sed -i '' -e $replace $template_dist_dir/*.template"
# sed -i '' -e $replace $template_dist_dir/*.template
# replace="s/%%BUCKET_NAME%%/$1/g"
# echo "sed -i '' -e $replace $template_dist_dir/*.template"
# sed -i '' -e $replace $template_dist_dir/*.template
# replace="s/%%BUCKET_NAME%%/$1/g"
# echo "sed -i '' -e $replace $template_dist_dir/*.template"
# sed -i '' -e $replace $template_dist_dir/*.template
# replace="s/%%SOLUTION_NAME%%/$2/g"
# echo "sed -i '' -e $replace $template_dist_dir/*.template"
# sed -i '' -e $replace $template_dist_dir/*.template
# replace="s/%%VERSION%%/$3/g"
# echo "sed -i '' -e $replace $template_dist_dir/*.template"
# sed -i '' -e $replace $template_dist_dir/*.template

echo "------------------------------------------------------------------------------"
echo "[Rebuild] CDK Solution"
echo "------------------------------------------------------------------------------"

# do we need a virtual environment, or are we using one now?
build_venv_name=".venv_build"
build_venv_dir="$template_dir/$build_venv_name"

# clean up testing venv if present
rm -rf $build_venv_dir

# check if we need a new testing venv
./venv_check.py
if [ "$?" == "1" ]; then
    echo 'creating temporary virtual environment for build'
    python3 -m venv $build_venv_name
    source $build_venv_name/bin/activate
    # configure the environment
    pip install --upgrade pip
    pip install --upgrade -r $source_dir/requirements.txt
else
    echo 'using currently activated virtual environment for build'
    echo 'deactivate your virtual environment to use a script-generated one'
fi

# generate the templates (unbundled)
cd $source_dir/
cdk synth -o $cdk_out
