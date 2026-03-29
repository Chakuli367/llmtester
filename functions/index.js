// functions/index.js
// Triggers on every new Firebase Auth signup → calls Flask → Playwright adds to Play Console

const functions = require("firebase-functions");
const axios = require("axios");

const RENDER_URL = functions.config().playconsole.render_url; // e.g. https://your-app.onrender.com/add-tester
const WEBHOOK_SECRET = functions.config().playconsole.webhook_secret;

exports.addTesterOnSignup = functions.auth.user().onCreate(async (user) => {
  const email = user.email;

  if (!email) {
    console.log("No email on user, skipping.");
    return;
  }

  console.log(`New user: ${email} — triggering Play Console add...`);

  try {
    const response = await axios.post(
      RENDER_URL,
      { email },
      {
        headers: { "X-Webhook-Secret": WEBHOOK_SECRET },
        timeout: 60000, // 60s — Playwright needs time
      }
    );
    console.log(`✅ Added ${email}:`, response.data);
  } catch (err) {
    console.error(`❌ Failed to add ${email}:`, err.message);
  }
});
