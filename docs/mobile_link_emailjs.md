# Mobile Link Emails With EmailJS

The mobile gate can send a desktop replay link through EmailJS when someone opens the replay viewer on a phone.

## EmailJS values

The current viewer already has these defaults from your EmailJS setup:

```text
Service ID: service_7zvgf1d
Template ID: template_8fhb9w1
Public Key: IxysEF7YkU8-Qnd-s
```

You can still set them as Hugging Face secrets so the deployed Space is explicit:

```text
REPLAY_VIEWER_EMAILJS_SERVICE_ID=service_7zvgf1d
REPLAY_VIEWER_EMAILJS_TEMPLATE_ID=template_8fhb9w1
REPLAY_VIEWER_EMAILJS_PUBLIC_KEY=IxysEF7YkU8-Qnd-s
```

If EmailJS requires the private key for REST calls, add it as a secret too:

```text
REPLAY_VIEWER_EMAILJS_PRIVATE_KEY=<your EmailJS private key>
```

Do not commit the private key to the repository.

The viewer also has a browser-side fallback. If EmailJS blocks server-side REST calls with `API access from non-browser environments is currently disabled`, the phone browser will try to send the same email directly through EmailJS after the server saves the request.

## Template fields

Keep the EmailJS template mapped like this:

```text
Subject: {{title}}
Content: {{{data}}}
To Email: {{to}}
From Name: {{name}}
Reply To: {{email}}
```

The backend generates the full HTML email and sends it as `data`. Use `{{{data}}}` with triple braces in EmailJS so the HTML is rendered instead of escaped as text. The email includes:

- a short explanation of the AI Catan Replay Viewer
- why desktop is recommended
- the replay link
- the selected session name
- Shon Levin's LinkedIn link: https://www.linkedin.com/in/shon-levin/

After a visitor email is sent, the viewer sends a second notification email to `levinshon@gmail.com` with:

- the visitor's email address
- the selected session
- the replay link that was sent

## What gets stored locally

Every mobile request is also appended to:

```text
examples/ai_testing/my_games/mobile_link_requests.jsonl
```

This gives you a fallback list even if EmailJS rejects a request or the monthly free quota is exhausted.
