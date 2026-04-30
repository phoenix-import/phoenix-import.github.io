# Contact Form Custom - Implementation Instructions

All files in this folder are ready to copy-paste into the live Dawn theme via
Shopify admin > Online Store > Themes > (your active theme) > Edit code.

---

## Step 1 - Check email routing first (do this before anything else)

Go to Shopify admin > Settings > Notifications. Scroll down and look for a
"Contact form" notification. If the recipient email is editable there, change
it to info@phoeniximport.nl and skip to Step 2.

If the recipient field is greyed out or missing, use the email forwarding
fallback instead:

In whatever email client handles orders@phoeniximport.nl, create a rule that
auto-forwards to info@phoeniximport.nl filtered on the subject line Shopify
uses for contact notifications. The subject is typically something like
"New message from [your store name]". Set it to forward and optionally skip
the inbox. Two minutes to set up, works forever.

---

## Step 2 - Add the section file

In the theme code editor, open the "Sections" folder. Click "Add a new section".
Name it exactly: contact-form-custom

Delete the placeholder content Shopify puts in the new file. Paste the entire
contents of sections/contact-form-custom.liquid from this folder. Save.

---

## Step 3 - Add the page template

In the theme code editor, open the "Templates" folder. Click "Add a new template".
Choose type: page. Name it exactly: contact-custom

Shopify will create page.contact-custom.json. Delete whatever placeholder JSON
it inserts. Paste the entire contents of templates/page.contact-custom.json
from this folder. Save.

---

## Step 4 - Add locale keys

This is the most repetitive step. You need to add the same block of keys to
six locale files. Each locale file is a large JSON object. You are adding one
new object inside the existing "sections" key.

Open the theme code editor > Locales folder.

For each language below, open the file listed and find the "sections" object.
Add a comma after the last entry in "sections", then paste the inner object
from the corresponding additions file.

The additions files in this folder only contain the new keys. Do not replace
the entire locale file - only add the new block inside "sections".

Language files to update:
- nl.default.json (or nl.json) - use contact-form-additions.nl.json
- en.default.json (or en.json) - use contact-form-additions.en.json
- de.json - use contact-form-additions.de.json
- fr.json - use contact-form-additions.fr.json
- it.json - use contact-form-additions.it.json
- es.json - use contact-form-additions.es.json

What you are pasting into each locale file looks like this (using NL as example):

  "contact_form_custom": {
    "label_company": "Bedrijfsnaam",
    ...all the keys...
  }

This object goes inside the existing "sections": { ... } block. Make sure the
JSON stays valid - use a JSON validator if unsure (jsonlint.com works fine).

---

## Step 5 - Assign the template to the contact page

Go to Shopify admin > Online Store > Pages. Open the contact page.
In the right sidebar, find "Theme template". Change it from the current value
to "contact-custom". Save the page.

The contact page now uses the new template.

---

## Step 6 - Test

Open the contact page in a private/incognito window.

Things to verify:

1. Form renders with all fields and the country code dropdown
2. Submit with a real email address - confirm the email arrives at info@
   (or orders@ if you are using email forwarding, then check it forwards)
3. No new customer record appears in Shopify admin > Customers after submission
4. Fill in the hidden honeypot field manually via browser devtools (set the
   value of input#ContactForm-url) and submit - the form should not submit
5. Check that the success message appears after a valid submission
6. Switch the storefront to each of the six languages and verify the labels
   render correctly (no raw translation keys like sections.contact_form_custom.xxx)

---

## Notes

Button style: the submit button uses Dawn's "button--secondary" class. In
Dawn's default light color scheme this renders as a filled dark button. If it
looks wrong in your specific color scheme, change "button--secondary" to
"button--primary" in the section file.

Country code default: Netherlands (+31) is the first option and therefore the
default selection. If you want a different default, reorder the options in the
select element in the section file.

Field repopulation on error: Shopify's classic contact form only repopulates
the email and message fields automatically on validation error. The other fields
(name, company, etc.) will be blank if the user gets an error and has to
resubmit. This is a Shopify limitation with the classic form tag and is
consistent with Dawn's own default contact form behavior.

Honeypot field name: the honeypot input is named contact[body_url]. This means
if a bot fills it in, the value appears in the email body. That is harmless and
intentional - it provides a clear signal in the rare case a bot submission gets
through client-side validation.
