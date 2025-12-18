# Setting Up GitHub Repository for AthenaInformation

Follow these steps to create and push your code to GitHub:

## Step 1: Create the Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `AthenaInformation`
3. Description: "Healthcare Facility Survey Data Dashboard"
4. Choose **Public** or **Private** (your choice)
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click **Create repository**

## Step 2: Add the New Remote

After creating the repository, GitHub will show you commands. Use this one:

```bash
git remote add athena-info https://github.com/DataScienceDan/AthenaInformation.git
```

Or if you want to replace the existing origin:

```bash
git remote set-url origin https://github.com/DataScienceDan/AthenaInformation.git
```

## Step 3: Stage and Commit Your Changes

```bash
# Add all important files
git add .gitignore
git add static/Dashboard.html
git add Dashboard.py
git add requirements.txt
git add Procfile
git add README.md

# Add data files (if you want to include them - they may be large)
# git add SurveySummaryAll.csv
# git add provider_info.csv
# git add health_deficiencies.csv

# Commit
git commit -m "Initial commit: Athena Information Dashboard with all features"
```

## Step 4: Push to GitHub

```bash
# If you added a new remote called 'athena-info'
git push -u athena-info main

# Or if you updated origin
git push -u origin main
```

## Step 5: Verify

1. Go to https://github.com/DataScienceDan/AthenaInformation
2. Verify all files are present
3. Check that README.md displays correctly

## Optional: Add Data Files Later

If your CSV files are large (>100MB), consider:
- Using Git LFS (Large File Storage)
- Or storing them separately and documenting where to get them
- Or adding them to .gitignore and providing download instructions

## Notes

- The `.gitignore` file excludes backups, cache files, and sensitive data
- Your API keys and tokens are already excluded
- Backups directory is excluded to keep the repo clean

