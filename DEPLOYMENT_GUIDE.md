# Deployment Guide for Athena Dashboard

This guide will help you deploy your Flask application to make it accessible to others.

## Prerequisites

1. **Git** installed on your computer
2. **GitHub account** (free) - for code hosting
3. **Deployment platform account** (see options below)

## Security First: Move API Keys to Environment Variables

⚠️ **IMPORTANT**: Your OpenAI API key is currently hardcoded in `Dashboard.py`. This must be changed before deployment!

### Step 1: Update Dashboard.py

Find this line in `Dashboard.py` (around line 2102):
```python
client = OpenAI(api_key="sk-proj-...")
```

Change it to:
```python
import os
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")
client = OpenAI(api_key=api_key)
```

### Step 2: Create a `.env` file (for local development)

Create a file named `.env` in your project root:
```
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

Add `.env` to `.gitignore` to prevent committing secrets:
```
.env
*.env
```

## Deployment Options

### Option 1: Render (Recommended - Free Tier Available)

**Pros**: Free tier, easy setup, automatic HTTPS, good for Flask apps

**Steps**:

1. **Prepare your code**:
   - Create a `render.yaml` file (see below)
   - Ensure `requirements.txt` is up to date
   - Make sure all data files are included or uploaded separately

2. **Create render.yaml**:
```yaml
services:
  - type: web
    name: athena-dashboard
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn Dashboard:app
    envVars:
      - key: OPENAI_API_KEY
        sync: false
    plan: free
```

3. **Deploy**:
   - Go to https://render.com
   - Sign up for free account
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect settings
   - Add environment variable: `OPENAI_API_KEY` = your key
   - Deploy!

**Note**: Free tier spins down after 15 minutes of inactivity. Upgrade to paid for always-on.

### Option 2: Railway (Easy Setup)

**Pros**: Simple deployment, good free tier, automatic HTTPS

**Steps**:

1. Go to https://railway.app
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Add environment variable: `OPENAI_API_KEY`
6. Railway auto-detects Flask and deploys

### Option 3: PythonAnywhere (Good for Beginners)

**Pros**: Free tier, Python-focused, easy file upload

**Steps**:

1. Sign up at https://www.pythonanywhere.com (free account)
2. Upload your files via Files tab
3. Create a new Web App (Flask)
4. Point it to your `Dashboard.py`
5. Add environment variables in Web tab → Environment variables
6. Reload web app

**Note**: Free tier has limitations (1 web app, limited CPU time)

### Option 4: DigitalOcean App Platform

**Pros**: Reliable, scalable, good documentation

**Steps**:

1. Create account at https://www.digitalocean.com
2. Go to App Platform
3. Connect GitHub repository
4. Configure:
   - Build command: `pip install -r requirements.txt`
   - Run command: `gunicorn Dashboard:app`
   - Environment variables: Add `OPENAI_API_KEY`
5. Deploy

**Cost**: ~$5-12/month for basic plan

## Required Files for Deployment

### 1. Create `Procfile` (for Heroku/Railway/Render)
```
web: gunicorn Dashboard:app
```

### 2. Update `requirements.txt` to include gunicorn:
```
Flask==2.3.3
pandas==2.1.1
openpyxl==3.1.2
Werkzeug==2.3.7
gunicorn==21.2.0
openai>=1.0.0
```

### 3. Update Dashboard.py for production

Change the last lines from:
```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

To:
```python
if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000)
    # Production uses gunicorn, so this won't run
```

### 4. Handle Data Files

Your application needs these data files:
- `SurveySummaryAll.xlsx` or `SurveySummaryAll.csv`
- `provider_info.csv`
- `health_deficiencies.xlsx`
- Other CSV files

**Options**:
- **Option A**: Include in repository (if not too large)
- **Option B**: Upload to cloud storage (S3, Google Cloud Storage) and load from there
- **Option C**: Use platform's file storage feature

## Quick Start: Render Deployment

1. **Fix API key** (see Security section above)

2. **Create Procfile**:
```
web: gunicorn Dashboard:app --bind 0.0.0.0:$PORT
```

3. **Update requirements.txt** to include gunicorn

4. **Push to GitHub**:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/athena-dashboard.git
git push -u origin main
```

5. **Deploy on Render**:
   - Connect GitHub repo
   - Set environment variable `OPENAI_API_KEY`
   - Deploy!

## Environment Variables to Set

- `OPENAI_API_KEY`: Your OpenAI API key
- `FLASK_ENV`: Set to `production` (optional)

## Testing Your Deployment

After deployment, test:
1. Can you access the site?
2. Does Section 1 (state/facility selection) work?
3. Does Section 2 (survey dates) load?
4. Does Section 8 (schedule generation) work with API calls?

## Troubleshooting

**Issue**: App crashes on startup
- Check logs for missing dependencies
- Ensure all data files are present
- Verify environment variables are set

**Issue**: API calls fail
- Verify `OPENAI_API_KEY` is set correctly
- Check API key hasn't expired
- Review API usage limits

**Issue**: Data files not found
- Ensure files are in repository or uploaded
- Check file paths are relative (not absolute)

## Cost Estimates

- **Render Free**: $0/month (with limitations)
- **Render Paid**: $7/month (always-on)
- **Railway**: $5/month (after free credits)
- **PythonAnywhere**: $0-5/month
- **DigitalOcean**: $5-12/month

## Need Help?

- Render Docs: https://render.com/docs
- Railway Docs: https://docs.railway.app
- Flask Deployment: https://flask.palletsprojects.com/en/latest/deploying/

