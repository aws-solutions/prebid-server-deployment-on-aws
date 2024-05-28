
### Applying Patches for Build or New Changes

* Clone the repository and checkout the release tag intended for your build
* Run the command `git apply patchfile` at the root of the cloned repository
* Perform your build


### Updating Patches

* After applying the existing patches above, make source changes as needed
* Run the command `git diff >patchfile` at the root of the cloned repository
* Move and replace the existing patch file
* Commit the patch file to the repository
