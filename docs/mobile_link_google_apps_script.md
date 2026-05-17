# Mobile Link Emails With Google Apps Script

The replay viewer can collect mobile email requests and forward them to a Google Apps Script Web App that sends the desktop link through your Gmail account.

## 1. Create the Apps Script

Open https://script.google.com, create a new project, and paste this code:

```javascript
const SHARED_SECRET = 'change-me-to-a-random-string';
const SENDER_NAME = 'AI Catan Replay Viewer';
const LINKEDIN_URL = 'https://www.linkedin.com/in/shon-levin/';

function doPost(e) {
  const data = JSON.parse(e.postData.contents || '{}');
  if (data.secret !== SHARED_SECRET) {
    return json({ ok: false, error: 'forbidden' }, 403);
  }

  const email = String(data.email || '').trim();
  const link = String(data.link || '').trim();
  const session = String(data.session || '').trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || !link) {
    return json({ ok: false, error: 'invalid request' }, 400);
  }

  const subject = 'Your AI Catan replay link is ready';
  const body =
    `Thanks for checking out the AI Catan Replay Viewer.\n\n` +
    `This is an experimental replay interface for Catan games played by AI agents. ` +
    `Instead of only seeing the final board, you can replay a recorded session step by step: ` +
    `the board state, player table talk, actions, dice rolls, resource changes, and parts of the AI decision trace.\n\n` +
    `It is built for a desktop screen because the board, timeline, logs, chat, audio, and analysis panel all need room to breathe.\n\n` +
    `Open the replay here:\n\n${link}\n\n` +
    (session ? `Session: ${session}\n\n` : '') +
    `Shon Levin: ${LINKEDIN_URL}\n`;

  const htmlBody = `
    <div style="margin:0;padding:0;background:#f3f6fb;font-family:Inter,Segoe UI,Arial,sans-serif;color:#172033;">
      <div style="max-width:640px;margin:0 auto;padding:36px 18px;">
        <div style="background:#ffffff;border:1px solid #dbe4f0;border-radius:14px;overflow:hidden;box-shadow:0 18px 48px rgba(15,23,42,0.12);">
          <div style="background:#111827;color:#ffffff;padding:28px 30px;">
            <div style="font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#93c5fd;">AI Catan Replay Viewer</div>
            <h1 style="margin:10px 0 0;font-size:28px;line-height:1.15;font-weight:900;">Your replay link is ready</h1>
          </div>
          <div style="padding:30px;">
            <p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:#334155;">
              Thanks for checking out the AI Catan Replay Viewer.
            </p>
            <p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:#334155;">
              This is an experimental replay interface for Catan games played by AI agents. Instead of only seeing the final board, you can replay a recorded session step by step.
            </p>
            <div style="margin:22px 0;padding:18px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;">
              <div style="font-size:13px;font-weight:900;color:#111827;margin-bottom:10px;">Inside the replay you can follow:</div>
              <ul style="margin:0;padding-left:20px;color:#475569;font-size:14px;line-height:1.75;">
                <li>the board state as it changes over time</li>
                <li>the table talk and recorded audio</li>
                <li>actions, dice rolls, and resource changes</li>
                <li>the AI decision trace behind interesting moves</li>
              </ul>
            </div>
            <p style="margin:0 0 24px;font-size:16px;line-height:1.65;color:#334155;">
              The viewer is best on a laptop or desktop because the board, timeline, logs, chat, audio, and analysis panel all need room to breathe.
            </p>
            <div style="margin:24px 0;text-align:center;">
              <a href="${escapeHtml(link)}" style="display:inline-block;background:#2f6fed;color:#ffffff;text-decoration:none;font-weight:900;border-radius:10px;padding:14px 22px;">Open the replay</a>
            </div>
            ${session ? `<div style="margin:22px 0;padding:14px 16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;color:#1e3a8a;font-size:14px;"><strong>Session:</strong> ${escapeHtml(session)}</div>` : ''}
            <p style="margin:24px 0 0;font-size:14px;line-height:1.6;color:#64748b;">
              Curious about the project or want to follow along?
              <a href="${LINKEDIN_URL}" style="color:#2f6fed;font-weight:800;text-decoration:none;">Connect with Shon Levin on LinkedIn</a>.
            </p>
          </div>
        </div>
        <p style="margin:18px 0 0;text-align:center;font-size:12px;color:#94a3b8;">
          Sent because this replay is much happier on a real screen.
        </p>
      </div>
    </div>
  `;

  MailApp.sendEmail({
    to: email,
    subject,
    body,
    htmlBody,
    name: SENDER_NAME,
  });

  return json({ ok: true });
}

function json(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

## 2. Deploy it

1. Click **Deploy** -> **New deployment**.
2. Select **Web app**.
3. Set **Execute as** to **Me**.
4. Set **Who has access** to **Anyone**.
5. Authorize the script.
6. Copy the Web App URL.

## 3. Configure Hugging Face Secrets

In your Space settings, add:

```text
REPLAY_VIEWER_MOBILE_EMAIL_WEBHOOK_URL=<your Apps Script Web App URL>
REPLAY_VIEWER_MOBILE_EMAIL_SECRET=<the same SHARED_SECRET from the script>
```

Restart the Space after adding the secrets.

## Notes

- Google Apps Script `MailApp` sends through the Google account that owns the script.
- Gmail consumer accounts have a lower daily recipient quota than Google Workspace accounts.
- The viewer still stores every request locally in `examples/ai_testing/my_games/mobile_link_requests.jsonl`, even if the email webhook is not configured.
