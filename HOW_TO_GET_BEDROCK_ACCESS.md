# How to Get AWS Bedrock Access to Anthropic Claude

## Step-by-Step Instructions

### Step 1: Open AWS Console

1. Go to [AWS Console](https://console.aws.amazon.com/)
2. Sign in with your AWS account credentials
3. Make sure you're in the correct region: **ap-south-1** (Mumbai)

### Step 2: Navigate to Bedrock

1. In the AWS Console search bar, type "Bedrock"
2. Click on "Amazon Bedrock" service
3. You should see the Bedrock dashboard

### Step 3: Request Model Access

1. In the left sidebar, click on **"Model access"** or **"Base models"**
2. Click the **"Request model access"** or **"Manage model access"** button
3. You'll see a list of available models

### Step 4: Find Anthropic Claude 3 Haiku

1. Scroll down to find **"Anthropic"** section
2. Look for **"Claude 3 Haiku"** model
3. The model ID should be: `anthropic.claude-3-haiku-20240307-v1:0`

### Step 5: Request Access

1. Check the box next to **"Claude 3 Haiku"**
2. Click **"Request model access"** button
3. You may need to fill out a use case form:
   - **Use Case**: Data extraction from documents
   - **Description**: Extracting structured data (exam dates, titles) from PDF documents
   - **Industry**: Government/Education
4. Click **"Submit"**

### Step 6: Wait for Approval

- **Approval time**: Usually **instant** (within seconds)
- Some accounts may take up to 15 minutes
- You'll receive an email confirmation when approved
- The status will change from "Pending" to "Access granted"

### Step 7: Verify Access

Once approved, you can verify access:

```bash
# Check if model is accessible
aws bedrock list-foundation-models --region ap-south-1 --query "modelSummaries[?contains(modelId, 'claude-3-haiku')]"
```

Or simply run the test script:

```bash
python3 test_bedrock_when_access_granted.py
```

## What If Access Is Denied?

If your request is denied:

1. **Check AWS Account Status**: Make sure your account is in good standing
2. **Verify Payment Method**: Ensure you have a valid payment method
3. **Contact AWS Support**: Open a support ticket explaining your use case
4. **Try Different Region**: Some regions may have different approval policies

## Alternative Models

If you cannot get access to Claude 3 Haiku, you can try:

### Option 1: Claude 3 Sonnet (More Powerful)
- Model ID: `anthropic.claude-3-sonnet-20240229-v1:0`
- Better quality but more expensive
- May have same access requirements

### Option 2: Claude 3 Opus (Most Powerful)
- Model ID: `anthropic.claude-3-opus-20240229-v1:0`
- Best quality but most expensive
- May have stricter access requirements

### Option 3: Claude 2.1 (Older Version)
- Model ID: `anthropic.claude-v2:1`
- Older model but may have easier access
- Less capable than Claude 3

## After Getting Access

Once you have access:

1. **No configuration changes needed** - `.env` is already configured correctly
2. **Restart the service**:
   ```bash
   docker-compose restart fastapi-app
   ```

3. **Run the test**:
   ```bash
   python3 test_bedrock_when_access_granted.py
   ```

4. **Expected results**:
   - ✅ Bedrock extractions: > 0
   - ✅ Structured data with exam dates and titles
   - ✅ `normalized_data` field populated in database
   - ✅ All tests pass

## Troubleshooting

### Error: "Model use case details have not been submitted"
- **Solution**: You haven't requested access yet. Follow steps above.

### Error: "Access denied"
- **Solution**: Your request was denied. Contact AWS Support.

### Error: "Invalid credentials"
- **Solution**: Check your AWS credentials in `.env` file

### Error: "Region not supported"
- **Solution**: Change `AWS_REGION` in `.env` to a supported region

## Cost Estimate

**Anthropic Claude 3 Haiku Pricing (ap-south-1):**
- Input: $0.00025 per 1K tokens (~$0.25 per 1M tokens)
- Output: $0.00125 per 1K tokens (~$1.25 per 1M tokens)

**For the test PDF:**
- Input tokens: ~2,000 tokens
- Output tokens: ~1,500 tokens
- **Cost per extraction**: ~$0.002 (less than 1 cent)

**For 1,000 PDFs:**
- Estimated cost: ~$2.00

Very affordable for production use!

## Support

If you need help:
1. Check AWS Bedrock documentation: https://docs.aws.amazon.com/bedrock/
2. AWS Support: https://console.aws.amazon.com/support/
3. AWS Bedrock pricing: https://aws.amazon.com/bedrock/pricing/
