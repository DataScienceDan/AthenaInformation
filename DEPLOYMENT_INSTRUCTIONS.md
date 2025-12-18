# Deployment Instructions for Athena Dashboard

This guide provides step-by-step instructions for deploying your Flask application to a web hosting service.

## Prerequisites

- A GitHub account (recommended for easy deployment)
- The data files: `SurveySummaryAll.csv`, `provider_info.csv`, `health_deficiencies.xlsx`
- Your OpenAI API key

---

## Option 1: Render (Recommended - Easiest)

Render is the easiest option since you already have a `render.yaml` file configured.

### Step 1: Prepare Your Code

1. **Update Dashboard.py to use environment variables** (instead of reading from file):
   - The code currently reads from `DanConwayKey.txt`
   - We'll modify it to read from environment variable `OPENAI_API_KEY`

2. **Push your code to GitHub**:
   ```bash
   git init  # if not already initialized
   git add .
   git commit -m "Initial commit for deployment"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

### Step 2: Deploy on Render

1. **Sign up/Login**: Go to https://render.com and sign up (free tier available)

2. **Create a New Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select your repository

3. **Configure the Service**:
   - **Name**: `athena-dashboard` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn Dashboard:app`
   - **Plan**: Select "Free" (or upgrade for production)

4. **Set Environment Variables**:
   - Go to "Environment" tab
   - Add: `OPENAI_API_KEY` = your OpenAI API key from `DanConwayKey.txt`
   - Add: `PYTHON_VERSION` = `3.11` (or your preferred version)

5. **Upload Data Files**:
   - After deployment, you'll need to upload your data files:
     - `SurveySummaryAll.csv`
     - `provider_info.csv`
     - `health_deficiencies.xlsx`
   - **Option A**: Use Render's file system (temporary - files reset on redeploy)
   - **Option B**: Use cloud storage (S3, Google Cloud Storage) and modify code to download
   - **Option C**: Include files in Git repository (if under size limits)

6. **Deploy**:
   - Click "Create Web Service"
   - Wait for build to complete (5-10 minutes)
   - Your app will be live at: `https://athena-dashboard.onrender.com` (or your custom domain)

### Step 3: Handle Data Files

Since Render's file system is ephemeral, you have three options:

**Option A: Include in Git** (if files are small enough):
```bash
git add SurveySummaryAll.csv provider_info.csv health_deficiencies.xlsx
git commit -m "Add data files"
git push
```

**Option B: Use Cloud Storage** (Recommended for large files):
- Upload files to AWS S3, Google Cloud Storage, or similar
- Modify `Dashboard.py` to download files on startup
- Add credentials as environment variables

**Option C: Use Render Disk** (Paid feature):
- Upgrade to a paid plan
- Use persistent disk storage

---

## Option 2: Railway (Modern & Easy)

Railway is another excellent option with a free tier.

### Step 1: Prepare Code

1. **Create `railway.json`** (optional):
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn Dashboard:app",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

2. **Push to GitHub** (same as Render)

### Step 2: Deploy on Railway

1. **Sign up**: Go to https://railway.app
2. **New Project** → "Deploy from GitHub repo"
3. **Select your repository**
4. **Add Environment Variables**:
   - `OPENAI_API_KEY` = your API key
5. **Upload Data Files**: Use Railway's volume storage or cloud storage
6. **Deploy**: Railway auto-detects Python and deploys

---

## Option 3: PythonAnywhere (Python-Specific)

Great for Python apps, free tier available.

### Step 1: Sign Up
- Go to https://www.pythonanywhere.com
- Create a free account

### Step 2: Upload Your Code

1. **Open Bash Console** in PythonAnywhere
2. **Clone your repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd YOUR_REPO_NAME
   ```

3. **Upload data files** via Files tab or use `wget`/`curl`

### Step 3: Configure

1. **Create Web App**:
   - Web tab → "Add a new web app"
   - Choose "Flask" → Python 3.10
   - Set path: `/home/YOUR_USERNAME/YOUR_REPO_NAME/Dashboard.py`

2. **Set Environment Variables**:
   - Web tab → "Environment variables"
   - Add: `OPENAI_API_KEY`

3. **Install Dependencies**:
   ```bash
   pip3.10 install --user -r requirements.txt
   ```

4. **Reload** your web app

---

## Option 4: Heroku (Classic Option)

### Step 1: Install Heroku CLI
- Download from https://devcenter.heroku.com/articles/heroku-cli

### Step 2: Login and Create App
```bash
heroku login
heroku create athena-dashboard
```

### Step 3: Set Environment Variables
```bash
heroku config:set OPENAI_API_KEY=your_api_key_here
```

### Step 4: Deploy
```bash
git push heroku main
```

### Step 5: Upload Data Files
- Use Heroku's file system (ephemeral) or cloud storage
- Or use Heroku Postgres for data storage

---

## Required Code Changes

Before deploying, you need to modify `Dashboard.py` to read the API key from environment variables instead of a file:

### Current Code (needs change):
```python
# Read API key from DanConwayKey.txt file
api_key = None
key_file_path = Path('DanConwayKey.txt')
if key_file_path.exists():
    with open(key_file_path, 'r') as f:
        api_key = f.read().strip()
```

### Updated Code:
```python
# Read API key from environment variable (for deployment) or file (for local development)
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    # Fallback to file for local development
    key_file_path = Path('DanConwayKey.txt')
    if key_file_path.exists():
        with open(key_file_path, 'r') as f:
            api_key = f.read().strip()

if not api_key:
    return jsonify({'error': 'OpenAI API key not found. Please set OPENAI_API_KEY environment variable or provide DanConwayKey.txt file.'}), 500
```

---

## Data File Handling Strategies

### Strategy 1: Include in Git (Simple, but limited)
- Works if files are < 100MB total
- Files are version controlled
- Easy to update

### Strategy 2: Cloud Storage (Recommended for production)
- Upload to AWS S3, Google Cloud Storage, or Azure Blob Storage
- Modify code to download on startup
- Add download function to `Dashboard.py`:

```python
import boto3  # for AWS S3
# or
from google.cloud import storage  # for GCS

def download_data_files():
    # Download files from cloud storage
    # Save to local directory
    pass
```

### Strategy 3: Database (Best for large datasets)
- Convert CSV/Excel to database (PostgreSQL, MySQL)
- Use SQL queries instead of pandas DataFrames
- More scalable and efficient

---

## Quick Start: Render Deployment (Step-by-Step)

1. **Update Dashboard.py** to use environment variables (see code changes above)

2. **Create GitHub repository**:
   ```bash
   git init
   git add .
   git commit -m "Ready for deployment"
   # Create repo on GitHub, then:
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

3. **Go to Render.com** → Sign up/Login

4. **New Web Service** → Connect GitHub → Select your repo

5. **Configure**:
   - Name: `athena-dashboard`
   - Environment: `Python 3`
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn Dashboard:app`
   - Plan: Free

6. **Environment Variables**:
   - `OPENAI_API_KEY`: (paste your key)

7. **Upload Data Files**:
   - Option A: Add to Git (if small)
   - Option B: Use Render's file system temporarily
   - Option C: Set up cloud storage

8. **Deploy** → Wait for build → Your app is live!

---

## Post-Deployment Checklist

- [ ] Test all functionality
- [ ] Verify API key is working
- [ ] Check data files are loading
- [ ] Test Section 2 deduplication
- [ ] Test Section 6 date validation
- [ ] Test Schedule generation
- [ ] Set up custom domain (optional)
- [ ] Configure SSL/HTTPS (usually automatic)
- [ ] Set up monitoring/alerts

---

## Troubleshooting

### Build Fails
- Check `requirements.txt` has all dependencies
- Verify Python version compatibility
- Check build logs for specific errors

### App Crashes on Startup
- Verify environment variables are set
- Check data files are accessible
- Review application logs

### Data Files Not Found
- Ensure files are in the correct location
- Check file paths in code match deployment structure
- Consider using absolute paths or environment variables for paths

### API Key Errors
- Verify `OPENAI_API_KEY` environment variable is set
- Check for extra spaces or newlines in the key
- Ensure the key is valid and has credits

---

## Security Notes

⚠️ **Important Security Considerations:**

1. **Never commit API keys to Git**
   - Use environment variables
   - Add `DanConwayKey.txt` to `.gitignore`
   - Add `ToDoToken.txt` to `.gitignore`

2. **Protect sensitive data**
   - Don't commit data files with sensitive information
   - Use environment variables for all secrets

3. **Rate Limiting**
   - Consider adding rate limiting to prevent abuse
   - Monitor API usage

---

## Cost Estimates

- **Render Free**: $0/month (with limitations)
- **Render Starter**: $7/month
- **Railway Free**: $5 credit/month (usually enough for small apps)
- **PythonAnywhere Free**: $0/month (limited)
- **Heroku**: No free tier anymore (starts at $5/month)

---

## Need Help?

If you encounter issues:
1. Check the deployment platform's documentation
2. Review application logs
3. Test locally first with environment variables
4. Verify all dependencies are in `requirements.txt`

