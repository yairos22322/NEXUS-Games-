@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title NEXUS FIVE 3D ULTRA - GitHub Publisher
color 0B

echo ==================================================
echo       NEXUS FIVE 3D ULTRA - GITHUB PUBLISHER
echo ==================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo Git was not found on this PC.
    echo Install Git for Windows from https://git-scm.com/download/win
    echo Then run this file again.
    pause
    exit /b 1
)

set /p REPO_URL=Paste your EMPTY GitHub repository HTTPS URL: 
if "%REPO_URL%"=="" (
    echo Repository URL cannot be empty.
    pause
    exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [1/6] Initializing Git repository...
    git init
    if errorlevel 1 goto :error
) else (
    echo [1/6] Git repository already initialized.
)

echo [2/6] Setting main branch...
git branch -M main
if errorlevel 1 goto :error

echo [3/6] Staging files...
git add .
if errorlevel 1 goto :error

echo [4/6] Creating commit...
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Initial release - NEXUS FIVE 3D ULTRA"
    if errorlevel 1 (
        echo.
        echo Git could not create the commit.
        echo If this is your first Git commit, configure your identity once:
        echo   git config --global user.name "Your Name"
        echo   git config --global user.email "you@example.com"
        echo Then run this publisher again.
        pause
        exit /b 1
    )
) else (
    echo No new staged changes. Continuing.
)

echo [5/6] Connecting GitHub repository...
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin "%REPO_URL%"
) else (
    git remote set-url origin "%REPO_URL%"
)
if errorlevel 1 goto :error

echo [6/6] Pushing to GitHub...
git push -u origin main
if errorlevel 1 goto :push_error

echo.
echo ==================================================
echo SUCCESS - Project pushed to GitHub.
echo ==================================================
pause
exit /b 0

:push_error
echo.
echo Push failed.
echo Make sure the repository is EMPTY and that GitHub authentication completed.
echo If GitHub asks for authentication, use Git Credential Manager / browser sign-in.
pause
exit /b 1

:error
echo.
echo A Git command failed. Read the error above.
pause
exit /b 1
