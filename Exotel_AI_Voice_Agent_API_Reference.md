# Exotel API Reference for AI Voice Agent — Call & SMS

> **Purpose:** Build an AI voice agent using Exotel as the telecom layer for both inbound/outbound calls and SMS, with an Indian Virtual Number (ExoPhone) as the customer-facing helpline. Your AI backend needs no Indian number of its own.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Authentication & Setup](#2-authentication--setup)
3. [Inbound Calls — Customer → ExoPhone → AI Agent](#3-inbound-calls--customer--exophone--ai-agent)
4. [Outbound Calls — AI Agent → Customer](#4-outbound-calls--ai-agent--customer)
5. [SMS Inbound — Receiving Customer Messages](#5-sms-inbound--receiving-customer-messages)
6. [SMS Outbound — AI Agent Replies](#6-sms-outbound--ai-agent-replies)
7. [Voice Streaming — Bidirectional Audio (Voicebot)](#7-voice-streaming--bidirectional-audio-voicebot)
8. [Applets Reference](#8-applets-reference)
9. [StatusCallback — Call & SMS Events](#9-statuscallback--call--sms-events)
10. [India-Specific Compliance (DLT / TRAI)](#10-india-specific-compliance-dlt--trai)
11. [Rate Limits & HTTP Status Codes](#11-rate-limits--http-status-codes)
12. [Pre-Launch Checklist](#12-pre-launch-checklist)

---

## 1. System Architecture

### Overview

```
Customer (calls or texts)
        │
        ▼
 ExoPhone (+91XXXXXXXXXX)   ← Indian Virtual Number visible to customer
        │
        ▼
  Exotel Platform
  ┌─────────────────────────┐
  │  App Flow (Applets)     │
  │  Greeting → Voicebot    │  ← For voice calls
  │  or SMS Webhook         │  ← For SMS
  └─────────────────────────┘
        │
        ▼
  Your AI Backend (no Indian number needed)
  ┌─────────────────────────────────────────┐
  │  WebSocket endpoint  (voice/audio)      │
  │  HTTP POST endpoint  (SMS webhook)      │
  │                                         │
  │  STT → LLM → TTS  (for voice)          │
  │  LLM              (for SMS replies)     │
  └─────────────────────────────────────────┘
```

### Two Communication Channels

| Channel | Direction | Exotel mechanism | Your AI role |
|---------|-----------|------------------|--------------|
| **Voice Call** | Inbound & Outbound | Voicebot Applet (WebSocket) | Receive audio stream, reply with TTS audio |
| **SMS** | Inbound & Outbound | SMS Webhook + Send SMS API | Receive POST with message body, reply via API |

### Key Concepts

| Term | Meaning |
|------|---------|
| **ExoPhone** | Indian virtual number (+91) provisioned by Exotel. Customers dial/SMS this. |
| **App Flow** | Call routing logic built with drag-and-drop Applets in the Exotel dashboard. |
| **Voicebot Applet** | Opens a **bidirectional WebSocket** between Exotel and your AI backend for real-time audio. |
| **Passthru Applet** | Webhooks to your URL on each call event; you return instructions (XML/JSON) to Exotel. |
| **StatusCallback** | POST from Exotel to your URL when a call or SMS reaches a terminal state. |
| **Mumbai cluster** | Use `@api.in.exotel.com` subdomain for Indian numbers — lower latency. |

---

## 2. Authentication & Setup

### Credentials

All API calls use **HTTP Basic Authentication**. Find your credentials in the Exotel dashboard under **API Settings → API Credentials**.

| Credential | Used as |
|------------|---------|
| `api_key` | HTTP Basic Auth username |
| `api_token` | HTTP Basic Auth password |
| `account_sid` | Appears in every API URL path |

### Base URLs

```
# India (Mumbai cluster) — use this for Indian ExoPhones
https://<api_key>:<api_token>@api.in.exotel.com/v1/Accounts/<account_sid>/

# Singapore cluster (if your account is on Singapore)
https://<api_key>:<api_token>@api.exotel.com/v1/Accounts/<account_sid>/
```

> **Use the Mumbai cluster** (`api.in.exotel.com`) for all Indian Virtual Numbers to ensure lowest call latency.

### Python auth pattern

```python
import requests

BASE_URL = "https://api.in.exotel.com/v1/Accounts/<account_sid>"
AUTH = ("<api_key>", "<api_token>")

response = requests.post(f"{BASE_URL}/Calls/connect", auth=AUTH, data={...})
```

---

## 3. Inbound Calls — Customer → ExoPhone → AI Agent

### How It Works

1. Customer dials your **ExoPhone** (+91 virtual number).
2. Exotel runs your **App Flow** (configured in the dashboard).
3. The **Voicebot Applet** opens a WebSocket to your AI backend.
4. Exotel streams caller audio to your server; your server streams TTS audio back.
5. On call end, Exotel fires a **StatusCallback** POST to your endpoint.

### App Flow Configuration (Dashboard)

In the Exotel dashboard, go to **Apps → Create App** and chain these applets:

```
[Greeting] → [Voicebot] → [Hangup]
```

- **Greeting:** Optional welcome message (upload .wav or use text-to-speech).
- **Voicebot:** Enter your WebSocket URL (e.g. `wss://your-ai.com/exotel/stream`).
- **Hangup:** Ends the call cleanly.

Assign this App to your ExoPhone under **Numbers → Configure**.

### Fetch Inbound Call Details

```
GET https://<api_key>:<api_token>@api.in.exotel.com/v1/Accounts/<sid>/Calls/<CallSid>.json
```

Use the `CallSid` received from Passthru webhook or StatusCallback to retrieve full call details after it ends.

**Response fields of interest:**

| Field | Description |
|-------|-------------|
| `Sid` | Unique call identifier |
| `From` | Customer's number |
| `To` | Your ExoPhone |
| `Status` | `completed`, `no-answer`, `busy`, `failed` |
| `Duration` | Call duration in seconds |
| `RecordingUrl` | URL to call recording (if enabled) |

---

## 4. Outbound Calls — AI Agent → Customer

### Connect Two Numbers API

Use this to have Exotel call two parties and bridge them — or to connect a customer to your AI backend.

```
POST https://<api_key>:<api_token>@api.in.exotel.com/v1/Accounts/<sid>/Calls/connect
```

Append `.json` to get a JSON response instead of XML.

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `From` | **Required** | Number connected **first**. For AI outbound, use your AI agent's SIP or number. |
| `To` | **Required** | Customer's mobile number. E.164 format: `+91XXXXXXXXXX`. |
| `CallerId` | **Required** | Your **ExoPhone** (Indian virtual number). This is what the customer sees. |
| `StreamUrl` | Optional | WebSocket URL for **unidirectional** audio streaming (caller audio → your server). |
| `StreamBegin` | Optional | `at Leg1Connect` or `at Leg2Connect` — when to start streaming. |
| `Record` | Optional | `true` / `false`. Records the call. Default: `false`. |
| `RecordingChannels` | Optional | `single` (default) or `dual` (separate channels per leg). |
| `RecordingFormat` | Optional | `mp3` (default) or `mp3-hq` (32 kbps — contact Exotel to enable). |
| `TimeLimit` | Optional | Max call duration in seconds. Maximum: `14400` (4 hours). |
| `TimeOut` | Optional | Ring timeout in seconds for both legs. |
| `WaitUrl` | Optional | `.wav` audio URL played to caller while waiting for the other leg to connect. |
| `StatusCallback` | Optional | Your URL to receive call completion data. |
| `StatusCallbackEvents` | Optional | Array: `terminal` (call ended) and/or `answered` (per leg answered). |
| `StatusCallbackContentType` | Optional | `multipart/form-data` (default) or `application/json`. |
| `CustomField` | Optional | Pass any string (e.g. order ID); returned in the terminal StatusCallback. |
| `CallType` | Optional | `trans` for transactional calls. |

### Python Example — Outbound with AI Streaming

```python
import requests

response = requests.post(
    "https://api.in.exotel.com/v1/Accounts/<account_sid>/Calls/connect",
    auth=("<api_key>", "<api_token>"),
    data={
        "From": "+91AI_AGENT_OR_SIP",          # Called first — your AI/agent side
        "To": "+91CUSTOMER_NUMBER",             # Customer's number
        "CallerId": "+91EXOPHONE",              # Shown to customer
        "StreamUrl": "wss://your-ai.com/exotel/stream",
        "StreamBegin": "at Leg2Connect",        # Start streaming once customer picks up
        "Record": "true",
        "StatusCallback": "https://your-ai.com/call-ended",
        "StatusCallbackEvents[0]": "terminal",
        "StatusCallbackEvents[1]": "answered",
        "StatusCallbackContentType": "application/json",
        "CustomField": "session_id_xyz",
    }
)
print(response.json())
```

### Success Response

```json
{
  "Call": {
    "Sid": "c5797dcbaaeed7678c4062a4a3ed2f8a",
    "Status": "in-progress",
    "From": "+91AI_AGENT",
    "To": "+91CUSTOMER",
    "PhoneNumberSid": "+91EXOPHONE",
    "Direction": "outbound-api",
    "RecordingUrl": null
  }
}
```

> **Note:** HTTP 200 means Exotel accepted the request — not that the call was answered. Check `StatusCallback` or the GET Call Details API for the final status.

### AnsweredBy Detection (Beta)

For the second call leg, Exotel can detect if a **human** or **voicemail** answered:

| Value | Meaning |
|-------|---------|
| `Human` | Call answered by a person |
| `Machine` | Voicemail or automated system |
| `NotSure` | Detection was inconclusive |

This is returned in the `StatusCallbackEvents` payload when `answered` events are enabled.

---

## 5. SMS Inbound — Receiving Customer Messages

### Configuration

In the Exotel dashboard, go to your **ExoPhone → Configure → SMS Inbound Webhook** and set your AI backend endpoint URL.

### Webhook Payload

When a customer texts your ExoPhone, Exotel sends a **POST** to your endpoint with:

| Field | Description |
|-------|-------------|
| `SmsSid` | Unique ID of the incoming SMS |
| `From` | Customer's mobile number |
| `To` | Your ExoPhone that received the SMS |
| `Body` | The customer's message text — feed this to your LLM |
| `AccountSid` | Your Exotel account SID |

### Python Handler Example

```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/sms-inbound", methods=["POST"])
def sms_inbound():
    customer_number = request.form.get("From")
    message_body = request.form.get("Body")
    sms_sid = request.form.get("SmsSid")

    # Pass message_body to your LLM
    ai_reply = your_llm_function(message_body)

    # Reply via Exotel Send SMS API
    reply_to_customer(customer_number, ai_reply)

    return "", 200
```

---

## 6. SMS Outbound — AI Agent Replies

### Send SMS API

```
POST https://<api_key>:<api_token>@api.in.exotel.com/v1/Accounts/<sid>/Sms/send
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `From` | **Required** | Your ExoPhone or DLT-registered Sender ID (e.g. `AIHELP`). Must be linked to your ExoPhone. |
| `To` | **Required** | Customer's mobile number. E.164: `+91XXXXXXXXXX`. |
| `Body` | **Required** | AI-generated reply text. Max 2000 characters. Must match your DLT-registered template. |
| `DltEntityId` | **Required (India)** | Your Entity ID from the DLT portal. Mandatory for all India SMS. |
| `DltTemplateId` | Recommended | Template ID from the DLT portal. Required if `SmsType` is not set. |
| `SmsType` | Optional | `transactional` / `transactional_opt_in` / `promotional`. Use `transactional` for AI helpline replies. |
| `StatusCallback` | Optional | URL to receive delivery status (`sent`, `failed`, `failed-dnd`). |
| `Priority` | Optional | `normal` (default) or `high`. Use `high` only for OTPs — misuse affects delivery. |
| `EncodingType` | Optional | `plain` or `unicode` (for non-Latin scripts like Tamil). |
| `CustomField` | Optional | Any string (e.g. session ID) — returned in StatusCallback. |

### Python Example — AI SMS Reply

```python
import requests

def reply_to_customer(customer_number: str, ai_reply_text: str) -> dict:
    response = requests.post(
        "https://api.in.exotel.com/v1/Accounts/<account_sid>/Sms/send",
        auth=("<api_key>", "<api_token>"),
        data={
            "From": "AIHELP",                      # Your DLT Sender ID
            "To": customer_number,                  # e.g. +919XXXXXXXXX
            "Body": ai_reply_text,
            "DltEntityId": "YOUR_DLT_ENTITY_ID",
            "DltTemplateId": "YOUR_TEMPLATE_ID",
            "SmsType": "transactional",
            "StatusCallback": "https://your-ai.com/sms-status",
            "CustomField": "session_xyz",
        }
    )
    return response.json()
```

### StatusCallback Payload (SMS Delivery)

Exotel POSTs these fields to your `StatusCallback` URL when SMS is delivered or fails:

| Field | Description |
|-------|-------------|
| `SmsSid` | Unique SMS identifier |
| `To` | Customer number |
| `Status` | `sent`, `failed`, `failed-dnd` |
| `DetailedStatus` | Human-readable status description |
| `DetailedStatusCode` | Exotel's internal status code |
| `DateSent` | Timestamp |
| `SmsUnits` | Number of SMS units used |
| `CustomField` | Your custom field if set |

---

## 7. Voice Streaming — Bidirectional Audio (Voicebot)

### Overview

The **Voicebot Applet** is the core integration for real-time AI voice conversations. Exotel opens a persistent WebSocket connection to your AI backend for the duration of the call.

```
Exotel ──── (caller audio) ────► Your AI WebSocket server
Exotel ◄─── (TTS audio)   ───── Your AI WebSocket server
```

> **Important:** Contact `hello@exotel.in` or your account manager to **enable WebSocket streaming** on your account before using the Voicebot Applet. It is not enabled by default.

### Audio Format Requirements

| Property | Value |
|----------|-------|
| Sample rate | 8000 Hz (standard telephony) |
| Encoding | μ-law (PCMU) — confirm with Exotel support for your account |
| Channels | Mono |
| Protocol | WebSocket (`wss://`) |

> Your STT model input **and** TTS output must both conform to this format. Resample if necessary using `ffmpeg` or `librosa`.

### Minimal WebSocket Server (Python + asyncio)

```python
import asyncio
import websockets

async def handle_exotel_call(websocket):
    """
    Exotel connects here for each call.
    Receives caller audio; sends back TTS audio.
    """
    async for message in websocket:
        if isinstance(message, bytes):
            # Step 1: message = raw audio from Exotel (customer speaking)
            # Step 2: Transcribe with STT (e.g. Whisper, Google STT)
            transcript = await your_stt(message)

            if transcript.strip():
                # Step 3: Generate reply with LLM
                reply_text = await your_llm(transcript)

                # Step 4: Synthesize speech with TTS
                audio_out = await your_tts(reply_text)

                # Step 5: Send audio back — Exotel plays it to the customer
                await websocket.send(audio_out)

async def main():
    async with websockets.serve(handle_exotel_call, "0.0.0.0", 8765):
        print("Voicebot WebSocket listening on wss://your-server:8765")
        await asyncio.Future()  # run forever

asyncio.run(main())
```

### Voice AI Stack Recommendation

```
Exotel (8kHz μ-law audio)
    │
    ▼
STT:  openai-whisper  (local GPU) or Google Cloud STT / Deepgram
    │
    ▼
LLM:  Claude (Anthropic API) or local model
    │
    ▼
TTS:  Google Cloud TTS / ElevenLabs / local TTS
    │
    ▼
Exotel (8kHz μ-law audio back)
```

### StreamUrl vs. Voicebot Applet — Key Difference

| Feature | `StreamUrl` (Calls/connect API param) | Voicebot Applet (App Flow) |
|---------|--------------------------------------|---------------------------|
| Direction | **Unidirectional** — caller audio → your server only | **Bidirectional** — audio both ways |
| Use case | Passive call monitoring / transcription | Full AI voice conversation |
| Setup | API parameter | Exotel dashboard App Flow |
| AI can speak back | No | **Yes** |

**For a two-way AI conversation, always use the Voicebot Applet.**

---

## 8. Applets Reference

Applets are the building blocks of your call flow. Configure them in the Exotel dashboard under **Apps**.

### Applets for AI Voice Agent

| Applet | Purpose | AI Agent Use |
|--------|---------|--------------|
| **Greeting** | Play a welcome message to the caller | Optional opening prompt before AI takes over |
| **Voicebot** | Bidirectional WebSocket audio stream | Primary integration point for AI voice |
| **Passthru** | Webhook to your URL; you return instructions | IVR-style control — gather intent, branch flows |
| **Gather** | Collect DTMF keypad input from caller | Offer menu options as fallback |
| **IVR Menu** | Multi-option menu | Pre-AI routing (press 1 for support, 2 for sales) |
| **Transfer** | Forward call to another number or flow | Escalate to human agent if AI fails |
| **Hangup** | End the call | Always chain at the end of your flow |
| **SMS Applet** | Send an SMS during or after a call | Send confirmation SMS after AI resolves the query |
| **Timing** | Route calls by time of day | Redirect after-hours calls to voicemail |

### Passthru Applet

Use Passthru as an alternative to Voicebot for IVR-style flows where you want fine-grained control per event.

**Webhook payload Exotel sends to your URL:**

| Field | Description |
|-------|-------------|
| `CallSid` | Unique call ID |
| `From` | Caller's number |
| `To` | Your ExoPhone |
| `CallStatus` | Current call status |
| `digits` | DTMF digits pressed (if after a Gather applet) |

**Your server must respond** with XML or JSON instructing Exotel what to do next (play audio, gather input, hang up, etc.).

---

## 9. StatusCallback — Call & SMS Events

### Call StatusCallback Fields

Exotel POSTs these to your `StatusCallback` URL when a call event fires:

| Field | Description |
|-------|-------------|
| `CallSid` | Unique call identifier |
| `From` | Caller's number |
| `To` | Called number |
| `CallStatus` | `completed`, `no-answer`, `busy`, `failed`, `in-progress` |
| `Direction` | `inbound` or `outbound-api` |
| `Duration` | Call duration in seconds |
| `RecordingUrl` | URL to call recording (if recording was enabled) |
| `AnsweredBy` | `Human`, `Machine`, or `NotSure` (Beta — second leg only) |
| `CustomField` | Your custom field value (terminal event only) |

### Event Types

| Event | When it fires |
|-------|---------------|
| `terminal` | Call has ended (with or without being answered) |
| `answered` | Each leg is answered (fires once per leg) |

### Setting Up StatusCallback

```python
data={
    "StatusCallback": "https://your-ai.com/call-events",
    "StatusCallbackEvents[0]": "terminal",
    "StatusCallbackEvents[1]": "answered",
    "StatusCallbackContentType": "application/json",
}
```

---

## 10. India-Specific Compliance (DLT / TRAI)

### What Is DLT?

TRAI (India's telecom regulator) mandates that all commercial SMS sent in India must be registered on a **Distributed Ledger Technology (DLT)** portal. This applies to any SMS your AI agent sends to customers.

### What You Must Register

| Item | Description |
|------|-------------|
| **Entity** | Your business. You get a unique **Entity ID**. |
| **Sender ID (Header)** | The name that appears as the sender, e.g. `AIHELP`. Max 6 characters. |
| **Templates** | Every SMS your AI might send must be pre-registered. Variable parts use `{#var#}` placeholders. |

### DLT Template Example

```
Your query has been received. Our AI agent will respond within {#var#} minutes. Ref: {#var#}.
```

> The message body you send via the API must match this template structure exactly. The `{#var#}` parts can be replaced with actual values.

### API Parameters for DLT Compliance

```python
data={
    "Body": "Your query has been received. Our AI agent will respond within 5 minutes. Ref: 98765.",
    "DltEntityId": "1234567890123456789",    # Your DLT Entity ID
    "DltTemplateId": "1234567890123456789",  # Template ID for this specific message
    "SmsType": "transactional",              # Match your DLT template type
}
```

### SMS Types

| Type | Use case |
|------|----------|
| `transactional` | Service messages, OTPs, query responses (default for AI helpline) |
| `transactional_opt_in` | Service messages requiring opt-in |
| `promotional` | Marketing messages (numeric sender ID, restricted hours) |

---

## 11. Rate Limits & HTTP Status Codes

### Rate Limits

| API | Limit | Exceeded response |
|-----|-------|-------------------|
| Voice (all voice APIs) | 200 calls/minute | HTTP 429 Too Many Requests |
| SMS | Platform-level limit | HTTP 503 Service Unavailable |

Contact your Exotel account manager for higher throughput limits.

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success — request accepted and processed |
| `202` | Accepted — request queued |
| `400` | Bad Request — malformed parameters or missing DLT details |
| `401` | Unauthorised — invalid or missing API credentials |
| `402` | Payment Required — action not on your plan or usage limit exceeded |
| `403` | Forbidden — credentials valid but no access to this resource |
| `404` | Not Found — resource (CallSid, SmsSid) does not exist |
| `429` | Too Many Requests — rate limit exceeded |
| `5xx` | Server error — retry after a short delay |

---

## 12. Pre-Launch Checklist

### Infrastructure

- [ ] **Buy an ExoPhone** — Indian virtual number (+91) from `my.exotel.com/numbers`. This is your customer-facing helpline number.
- [ ] **Choose the Mumbai cluster** — use `api.in.exotel.com` for all API calls to minimise latency.
- [ ] **Get API credentials** — API key, API token, and Account SID from the Exotel dashboard under API Settings.

### Voice AI Setup

- [ ] **Enable WebSocket streaming** — contact `hello@exotel.in` or your account manager to activate the Voicebot Applet for your account.
- [ ] **Build your App Flow** in the Exotel dashboard: `Greeting → Voicebot (your wss:// URL) → Hangup`.
- [ ] **Assign the App Flow to your ExoPhone** under Numbers → Configure.
- [ ] **Test your WebSocket server** handles 8kHz μ-law audio correctly.
- [ ] **Implement latency monitoring** — target < 500ms round-trip for STT + LLM + TTS to keep conversation natural.

### SMS Setup

- [ ] **Register on DLT portal** — register your business entity, Sender ID, and all AI reply templates.
- [ ] **Note your DLT Entity ID and Template IDs** — required for every outbound SMS API call.
- [ ] **Configure SMS inbound webhook** on your ExoPhone in the Exotel dashboard.
- [ ] **Test DLT template matching** — verify SMS body matches registered template structure before going live.

### Callbacks & Monitoring

- [ ] **Set StatusCallback URLs** for both calls and SMS.
- [ ] **Log all CallSids and SmsSids** for debugging.
- [ ] **Implement retry logic** for HTTP 429 and 503 responses.
- [ ] **Set up call recording** (`Record: true`) for quality assurance and AI training data.

---

## Quick Reference — API Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| Make/connect a call | POST | `/v1/Accounts/<sid>/Calls/connect` |
| Get call details | GET | `/v1/Accounts/<sid>/Calls/<CallSid>.json` |
| Get all call details | GET | `/v1/Accounts/<sid>/Calls.json` |
| Send SMS | POST | `/v1/Accounts/<sid>/Sms/send` |
| Get SMS details | GET | `/v1/Accounts/<sid>/Sms/Messages/<SmsSid>.json` |
| List ExoPhones | GET | `/v1/Accounts/<sid>/IncomingPhoneNumbers.json` |

---

## Useful Links

- Exotel Developer Portal: `https://developer.exotel.com/api`
- Exotel Dashboard: `https://my.exotel.com`
- Applets documentation: `https://developer.exotel.com/applet`
- DLT compliance guide: Exotel Support → TRAI Regulations
- Voicebot / Streaming setup: `https://support.exotel.com/support/solutions/articles/3000108630`
- Enable streaming: contact `hello@exotel.in`

---

*Document covers Exotel Voice v1 API, SMS API, and Voicebot Applet as of April 2026.*
