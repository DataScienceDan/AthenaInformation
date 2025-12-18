# Quick Deployment Guide - Render.com

## Fastest Way to Deploy (5 Steps)

### Step 1: Update Code for Environment Variables ✅
**DONE** - Dashboard.py now reads from `OPENAI_API_KEY` environment variable

### Step 2: Push to GitHub

```bash
# If you haven't initialized git yet:
git init

# Add all files (API keys are already in .gitignore)
git add .

# Commit
git commit -m "Ready for deployment"

# Create a new repository on GitHub.com, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### Step 3: Deploy on Render

1. **Go to**: https://render.com
2. **Sign up** (free account works)
3. **Click**: "New +" → "Web Service"
4. **Connect**: Your GitHub account → Select your repository
5. **Configure**:
   - **Name**: `athena-dashboard` (or any name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn Dashboard:app`
   - **Plan**: Free (or upgrade later)
6. **Environment Variables**:
   - Click "Environment" tab
   - Add: `OPENAI_API_KEY` = (paste your key from DanConwayKey.txt)
7. **Click**: "Create Web Service"
8. **Wait**: 5-10 minutes for build

### Step 4: Upload Data Files

After deployment, you need to get your data files to Render:

**Option A: Include in Git** (if files are < 100MB):
```bash
git add SurveySummaryAll.csv provider_info.csv health_deficiencies.xlsx
git commit -m "Add data files"
git push
```

**Option B: Use Render Shell** (temporary):
1. Go to Render dashboard → Your service → "Shell"
2. Upload files via `wget` or use Render's file upload feature
3. **Note**: Files will be lost on redeploy (use Option C for permanent)

**Option C: Cloud Storage** (recommended):
- Upload files to AWS S3, Google Drive, or Dropbox
- Modify Dashboard.py to download files on startup
- More complex but permanent

### Step 5: Test Your Deployment

1. Visit your Render URL: `https://athena-dashboard.onrender.com`
2. Test all functionality
3. Check logs if something doesn't work

---

## Troubleshooting

**Build fails?**
- Check `requirements.txt` has all packages
- Verify Python version (3.9+)

**App crashes?**
- Check environment variables are set
- Verify data files exist
- Check logs in Render dashboard

**Data files missing?**
- Ensure files are in Git or uploaded
- Check file paths in code

---

## Your App Will Be Live At:
`https://YOUR-SERVICE-NAME.onrender.com`

You can share this URL with others!
