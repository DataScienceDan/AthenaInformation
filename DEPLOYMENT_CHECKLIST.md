# Pre-Deployment Checklist

## ✅ Code Changes Made

- [x] Updated `Dashboard.py` to read API key from environment variable `OPENAI_API_KEY`
- [x] Updated `Procfile` for Render compatibility
- [x] Fixed OpenAI model name (changed from "gpt-5" to "gpt-4o")
- [x] `.gitignore` already protects sensitive files

## 📋 Before You Deploy

### 1. Test Locally with Environment Variable

Test that the environment variable works:

**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY="your-key-here"
python Dashboard.py
```

**Windows CMD:**
```cmd
set OPENAI_API_KEY=your-key-here
python Dashboard.py
```

**Mac/Linux:**
```bash
export OPENAI_API_KEY="your-key-here"
python Dashboard.py
```

### 2. Prepare Your Data Files

Decide how to handle these files:
- `SurveySummaryAll.csv` (check size)
- `provider_info.csv` (check size)
- `health_deficiencies.xlsx` (check size)

**If total < 100MB**: Include in Git
**If total > 100MB**: Use cloud storage or Render's file system

### 3. Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository (make it private if you want)
3. Don't initialize with README (you already have files)

### 4. Push to GitHub

```bash
git add .
git commit -m "Ready for deployment"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 5. Deploy on Render

Follow the instructions in `QUICK_DEPLOY.md` or `DEPLOYMENT_INSTRUCTIONS.md`

---

## 🔧 Post-Deployment

1. **Test the live site**
2. **Check logs** if anything fails
3. **Share the URL** with users
4. **Monitor usage** and API costs

---

## 💡 Tips

- Start with Render's free tier to test
- Upgrade to paid plan if you need persistent storage
- Consider using a database instead of CSV files for better performance
- Set up monitoring/alerts for production use

