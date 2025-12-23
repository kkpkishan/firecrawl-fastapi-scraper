# AWS Bedrock Extraction Status

## Summary

AWS Bedrock extraction is **NOT working** for two reasons:

1. **Anthropic Claude 3 Haiku**: Requires model access approval (not granted yet)
2. **Amazon Titan**: Model is accessible but **cannot follow structured extraction instructions**

## Error Message

```
ResourceNotFoundException: Model use case details have not been submitted for this account. 
Fill out the Anthropic use case details form before using the model. 
If you have already filled out the form, try again in 15 minutes.
```

## Current Status

- ✅ AWS credentials are configured correctly
- ✅ Bedrock extraction is enabled in `.env`
- ✅ Application can connect to AWS Bedrock API
- ❌ **Model access not granted** - Need to request access to Claude model

## Test Results

### Test 1: Anthropic Claude 3 Haiku

**PDF Tested:** https://upsc.gov.in/sites/default/files/Calendar-2026-Engl-150525_5.pdf

**Error:**
```
ResourceNotFoundException: Model use case details have not been submitted for this account.
```

**Results:**
- Bedrock extractions: **0** (access denied)
- Regex extractions: 51 (fallback worked)

### Test 2: Amazon Titan Text Express

**PDF Tested:** https://upsc.gov.in/sites/default/files/Calendar-2026-Engl-150525_5.pdf

**Error:**
```
The model cannot find sufficient information to answer the question.
```

**Results:**
- Bedrock extractions: **0** (model refused to extract)
- Regex extractions: 51 (fallback worked)

**Conclusion:** Amazon Titan is not suitable for structured data extraction tasks. It cannot follow the JSON schema instructions properly.

## How to Fix

### Step 1: Request Model Access in AWS Console

1. Go to AWS Console → Bedrock → Model access
2. Click "Request model access" or "Manage model access"
3. Find "Anthropic Claude 3 Haiku" in the list
4. Click "Request access" and fill out the use case form
5. Submit the form

### Step 2: Wait for Approval

- Approval is usually instant for most models
- Some models may take up to 15 minutes
- You'll receive an email confirmation when approved

### Step 3: Verify Access

After approval, run the test again:

```bash
python3 test_pdf_extraction.py
```

You should see:
- Bedrock extractions: > 0
- Structured data with exam dates and titles
- `normalized_data` field populated in database

## Recommendation

**You MUST use Anthropic Claude models for structured data extraction.**

Amazon Titan models are NOT suitable because:
- They cannot follow complex JSON schema instructions
- They refuse to extract data when the task is complex
- They return generic error messages instead of structured data

**Required Action:**
1. Request access to **Anthropic Claude 3 Haiku** in AWS Bedrock console
2. Wait for approval (usually instant)
3. Keep the model configured as: `BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0`

## Alternative: Use Different Model

If you can't get access to Claude 3 Haiku, you can use Amazon Titan models which may have instant access:

**Option 1: Amazon Titan Text Express**
```bash
# In .env file
BEDROCK_MODEL_ID=amazon.titan-text-express-v1
```

**Option 2: Amazon Titan Text Lite**
```bash
# In .env file
BEDROCK_MODEL_ID=amazon.titan-text-lite-v1
```

Then restart the service:
```bash
docker-compose restart fastapi-app
```

## Current Fallback Behavior

The system is working correctly with fallback:
1. Tries Bedrock extraction first
2. If Bedrock fails → Falls back to regex extraction
3. Data is still extracted and stored (using regex patterns)

So the application is **functional**, but not using the advanced LLM extraction capabilities.

## What Bedrock Would Provide

Once access is granted, Bedrock will provide:

1. **Structured extraction** with schema validation
2. **Intelligent understanding** of exam dates and titles
3. **Normalized data** in JSON format:
   ```json
   {
     "page_info": {
       "title": "UPSC Examination Calendar 2026",
       "summary": "Programme of examinations and recruitment tests for 2026"
     },
     "extracted_fields": [
       {
         "key": "Exam Name",
         "value": "Civil Services (Preliminary) Examination, 2026",
         "confidence": "high"
       }
     ],
     "dates": [
       {
         "label": "Exam Date",
         "value": "2026-05-24",
         "context": "Civil Services (Preliminary) Examination"
       }
     ]
   }
   ```

## Next Steps

1. **Request model access** in AWS Bedrock console
2. **Wait for approval** (usually instant)
3. **Re-run test** to verify Bedrock extraction works
4. **Remove this file** after verification

## Contact

If you need help requesting model access, refer to:
- AWS Bedrock Documentation: https://docs.aws.amazon.com/bedrock/
- AWS Support: Open a support ticket if access is denied
