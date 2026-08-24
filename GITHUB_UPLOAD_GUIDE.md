# Upload NEXUS FIVE 3D ULTRA to GitHub

## Recommended method: included publish script

1. Sign in to GitHub.
2. Create a new EMPTY repository named `NEXUS-FIVE-3D-ULTRA`.
3. Do not add a README, `.gitignore`, or license on GitHub because this project already contains the repository files.
4. Copy the HTTPS repository URL. It will look like:
   `https://github.com/YOUR-USERNAME/NEXUS-FIVE-3D-ULTRA.git`
5. Open this project folder.
6. Double-click `PUBLISH_TO_GITHUB.bat`.
7. Paste the repository URL when asked.
8. Sign in to GitHub if Git asks you to authenticate.

The script creates the local Git repository, commits the project, sets the `main` branch, connects the GitHub remote, and pushes it.

## Browser-only method

1. Create a new repository on GitHub.
2. Keep it empty when creating it.
3. Open the new repository.
4. Choose `Add file` -> `Upload files`.
5. Drag the CONTENTS of this extracted project folder into the upload page.
6. Commit the uploaded files.

Important: do not upload the ZIP as the only repository file. GitHub does not unpack it into source code for you. Extract the ZIP first and upload its contents.

## Public or private?

- Public: anyone can view and clone the source.
- Private: only you and people you explicitly grant access to can view it.

This package intentionally does not select an open-source license for you. A public repository without a license is viewable, but it does not automatically grant broad reuse rights. Choose a license later only if that matches what you want.
