# Prebid Server Default Configuration

## Overview
This directory contains the **default configuration files** for setting up the Prebid Server environment. These files are intended to provide a baseline configuration for the Prebid Server and should not be altered directly. Any changes to the configuration should be handled as described below.

## Structure of the Configuration
The default configuration files are downloaded from the S3 bucket under the `/prebid-server/default/` prefix. These files include essential settings, scripts, and configurations that are required to start the Prebid Server containers properly.

**Note**: S3 bucket versioning is enabled for recovery purposes. This allows you to restore previous versions of any configuration file if needed. If a file is accidentally modified or deleted, you can revert to an earlier version.

## Usage
The default configuration files are used automatically when the script `bootstrap.sh` is executed. The script downloads the files from the specified S3 bucket and places them in the local `/prebid-configs` directory.

By design, these files should **NOT** be modified directly. They serve as a fallback or template that provides consistent defaults across all environments.

## How to Modify Configuration Files
If you need to make any changes to the configuration, please adhere to the following guidelines:

1. **Do not modify files in the `/prebid-server/default/` prefix**. These are intended to remain unchanged to provide a stable baseline configuration.
2. Any configuration overrides or changes should be placed in the `/prebid-server/current/` prefix of the S3 bucket. The `current` folder is meant for custom configurations and will take precedence over the default settings.

### Steps to Customize Configurations
1. **Create a Custom Configuration**: If a default file needs modifications, copy it from the `/prebid-server/default/` folder and place it in the `/prebid-server/current/` folder of the S3 bucket.
2. **Edit the Custom Configuration**: Make the necessary changes in the file that was copied to the `current` folder.
3. **Deploy the Custom Configuration**: When the `bootstrap.sh` script is executed, it will download the files from both the `default` and `current` folders, using the `current` folder files to override any defaults.

   To apply the new configuration, you need to force a redeployment of your container cluster. Follow the instructions provided in the [AWS ECS Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-console-v2.html) to initiate a redeployment and ensure that your changes are active.

## Why Use a `current` Folder?
This separation between `default` and `current` folders ensures that:

- **Default settings remain consistent**: The default files act as a template and safety net, which prevents accidental modifications that could affect the server's stability.
- **Custom settings are easily managed**: All custom configurations are grouped together, making them easy to manage, update, and review without the risk of affecting the default baseline.

## Folder Structure
- **`/prebid-server/default/`**: Contains the default configuration files. These files are the baseline setup for the Prebid Server and should not be altered.
- **`/prebid-server/current/`**: Place your custom configuration files here. Any files in this folder will take precedence over those in the `default` folder.

By following this structure, you'll maintain a clean separation between the stable default configuration and any custom adjustments required for your specific environment.

## Important Notes
- **Versioning for Recovery**: Since S3 bucket versioning is enabled, you can recover any previous versions of your configuration files if necessary.
- **Always back up** any configuration files before making changes.
- **Test thoroughly** before deploying changes to the `current` folder to ensure stability and correctness.
- **Forcing a Redeployment**: After making changes and uploading them to the `current` folder, force a redeployment of your container cluster to apply the new configuration as described [here](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-console-v2.html).
