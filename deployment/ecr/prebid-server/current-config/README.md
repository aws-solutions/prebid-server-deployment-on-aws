# Prebid Server Custom Configuration

## Overview
The `current/` folder is designed for **custom configurations** of the Prebid Server. Unlike the `default/` folder, which contains the baseline setup, this directory allows you to override and customize configuration files to fit your specific environment or requirements.

## Purpose of the `current/` Folder
The `current/` folder serves as a space for you to make any adjustments or changes to the default settings without altering the original baseline configurations stored in the `default/` folder. The files in `current/` take precedence over those in `default/` when the configuration is loaded by the `bootstrap.sh` script.

**Note**: S3 bucket versioning is enabled for recovery purposes. This allows you to restore previous versions of any custom configuration file if needed. If a file is accidentally modified or deleted, you can revert to an earlier version.

## How to Customize Configuration Files
1. **Identify the File to Modify**: Start by identifying which default configuration file needs to be customized. Check the `default/` folder to find the base version of the file.
2. **Copy the Default File**: Copy the necessary file(s) from the `default/` folder into the `current/` folder.
3. **Edit the File in the `current/` Folder**: Make the required changes to the file(s) in the `current/` folder. Since the `bootstrap.sh` script gives precedence to files in `current/`, your customized settings will override the default values.
4. **Test Your Changes**: It's important to thoroughly test any changes made in the `current/` folder before deploying them to a live environment.
5. **Deploy the Custom Configuration**: Once changes are made and tested, upload them to the `current/` folder in the S3 bucket. To apply the new configuration, you need to force a redeployment of your container cluster. Follow the instructions provided in the [AWS ECS Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-console-v2.html) to initiate a redeployment and ensure that your changes are active.

## Best Practices for Custom Configuration
- **Do Not Modify the `default/` Folder Directly**: Always make a copy of the file from `default/` and place it in the `current/` folder for modifications.
- **Keep Changes Minimal and Clear**: Only override the parts of the configuration that need customization. This keeps the custom settings clear and manageable.
- **Document Changes**: Include comments in the configuration files detailing what changes were made and why. This helps with debugging and understanding custom behavior in the future.

### Example
If you need to change the logging level for Prebid Server, follow these steps:
1. **Find `prebid-logging.xml` in `default/`**: Locate the `prebid-logging.xml` file in the `default/` folder of the S3 bucket.
2. **Copy to `current/`**: Copy the file to the `current/` folder: `s3://<bucket-name>/prebid-server/current/prebid-logging.xml`
3. **Edit and Customize**: Open the `prebid-logging.xml` file from the `current/` folder and modify the logging level or any other settings as needed.
4. **Deploy and Test**: Deploy the updated file to S3, and force a redeployment of your container cluster as detailed [here](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-console-v2.html).

## How the Script Works with the `current/` Folder
When the `bootstrap.sh` script is executed:
- It first downloads all files from the `default/` folder to set up the baseline configuration.
- Then, it downloads any files from the `current/` folder, which will override or add to the existing configuration from `default/`.
- The script verifies the existence of required configuration files and then starts the Prebid Server containers using the entrypoint script.

## Important Notes
- **Versioning for Recovery**: Since S3 bucket versioning is enabled, you can recover any previous versions of your configuration files if necessary.
- **Always back up** any configuration files before making changes.
- **Test thoroughly** before deploying changes to the `current/` folder to ensure stability and correctness.
- **Forcing a Redeployment**: After making changes and uploading them to the `current/` folder, force a redeployment of your container cluster to apply the new configuration as described [here](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-console-v2.html).
