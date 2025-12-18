# How to Verify Restored Features Are Working

## Quick Verification Steps

### 1. **Collapsible Sections** ✅
**How to verify:**
- Open the dashboard in your browser
- Look at ANY section header (e.g., "Facility Selection", "Health Survey Dates")
- You should see a **▼ (down arrow) button** on the right side of each section header
- **Click the header or the arrow button** - the section content should collapse/hide
- The arrow should change to **▶ (right arrow)** when collapsed
- Click again to expand

**What to look for:**
- All 9 sections should have collapse buttons
- Sections should smoothly collapse/expand when clicked

---

### 2. **Section 2: Deduplication & Facility Names** ✅
**How to verify:**
1. Select a state (e.g., "Florida")
2. Select a facility (e.g., "Advinia Care at of Naples" - CCN 105995)
3. Look at Section 2 "Health Survey Dates"
4. Scroll down to the "All Survey Dates" list

**What to look for:**
- **No duplicate dates** - each date should appear only once
- **Facility names** - each date should show: `Date - Facility Name`
- The facility name should match the provider name from Section 1
- Timeline should show dates ending in **December 2027** (not 2026)

**Example of correct format:**
```
All Survey Dates
- 1/15/2020 - Advinia Care at of Naples
- 3/22/2021 - Advinia Care at of Naples
- 6/10/2022 - Advinia Care at of Naples
```

---

### 3. **Section 6: Date Validation & Dynamic Prompt** ✅
**How to verify:**

**Date Validation:**
1. Go to Section 6 "Forecasts"
2. Scroll to the "Select Date of Expected Next Visit" calendar
3. Try to select a date less than 1 week from today
4. The calendar should **prevent** you from selecting dates too soon
5. The earliest selectable date should be 7 days from today

**Dynamic Prompt:**
1. Select a date that is **1-2 weeks away** (e.g., 10 days from today)
2. Click "Generate Prompt"
3. Look at the generated prompt in Section 8
4. The prompt should mention: `"the next X days (approximately Y week(s))"`
5. The schedule intervals should be short-term (e.g., "5 days before", "3 days before")

**Test with different timeframes:**
- **1-2 weeks**: Should show immediate preparation schedule
- **1-2 months**: Should show short-term preparation
- **3-6 months**: Should show medium-term preparation (90, 60, 30 days before)
- **6+ months**: Should show "6 months before (start date)" and full schedule

---

### 4. **Section 8: Get Schedule Button Messages** ✅
**How to verify:**
1. Generate a prompt in Section 6 (or use an existing one)
2. Go to Section 8 "Prompt for Schedule Generation"
3. Click the **"Get Schedule"** button
4. **Immediately** you should see an alert: 
   - "The schedule generation request has been submitted. This may take several minutes to complete. You will be notified when the result is ready."
5. Wait for the schedule to generate (may take 2-5 minutes)
6. When complete, you should see **another alert**:
   - "Schedule generation complete! The results are now available in Section 9."
7. Section 9 should automatically appear and scroll into view

---

### 5. **Timeline End Dates: December 2027** ✅
**How to verify:**
- Look at any timeline in the dashboard (Section 2, Section 3, Section 6)
- Check the scale at the bottom of each timeline
- The **last date** should show: **12/31/2027** (not 12/31/2026)

---

## Troubleshooting

### If collapse buttons don't appear:
1. **Hard refresh** your browser: `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac)
2. Check browser console for JavaScript errors: Press `F12` → Console tab
3. Verify the CSS is loaded - look for `.collapse-btn` styles in browser DevTools

### If Section 2 shows duplicates:
1. Check browser console for errors
2. Verify the API endpoint `/api/provider-names/{ccn}` is working
3. Check that the facility CCN is being passed correctly

### If date validation doesn't work:
1. Clear browser cache
2. Check that the date input has a `min` attribute set
3. Verify JavaScript console for errors

### If prompt isn't dynamic:
1. Check the generated prompt text in Section 8
2. Look for phrases like "Time available for preparation:"
3. Verify the schedule intervals change based on selected date

---

## Visual Checklist

When you open the dashboard, you should see:

- [ ] All section headers have ▼ buttons on the right
- [ ] Clicking headers collapses/expands sections
- [ ] Section 2 shows unique dates with facility names
- [ ] Section 6 date picker prevents dates < 1 week
- [ ] Generated prompts adjust based on time until date
- [ ] Get Schedule button shows alerts
- [ ] All timelines end in 2027

---

## Still Not Working?

If features still don't work after a hard refresh:

1. **Check the file**: Open `static/Dashboard.html` and search for:
   - `REQUIRED FEATURE` - should find multiple comments
   - `toggleSection` - should find the function
   - `collapse-btn` - should find CSS and HTML
   - `addTimelineMarkers` - should be `async function`
   - `generatePrompt` - should have dynamic time calculation

2. **Verify file was saved**: Check file modification time

3. **Check for syntax errors**: Use browser DevTools Console (F12)

4. **Restart the Flask server**: Stop and restart `python Dashboard.py`

