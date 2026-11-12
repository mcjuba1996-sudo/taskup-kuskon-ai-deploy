# Meeting registration: a three-state prototype

**Synthetic demo artifact prepared by the Kuskon AI team with Codex.** A shared example for fictional profiles, not the work of a real school student. There is no real meeting, registration or notification delivery.

Open `signup.html` in a browser. The single HTML file contains styles and JavaScript; it requires no server, libraries, network connection or personal data.

## Three states

1. **Registration.** A description of a free fictional meeting, its duration and a choice of two time slots. An empty selection fails the built-in form validation.
2. **Confirmation.** The selected time, duration and time zone are shown. Registration can be cancelled; the page explicitly explains that it is a demo.
3. **Cancellation.** The registration is cleared without asking for a reason. A button returns to the form so a time can be selected again.

Reloading the page restores the initial state. Only page memory is used: there are no cookies, `localStorage`, network requests, analytics or saved participant records.

## Why these decisions were made

The demonstration does not need a name, phone number, email address or free text. A time slot is selected from a list, making the confirmed choice clearer. Cancellation does not require an explanation. Fields have labels and buttons can be reached by keyboard; changing state moves focus to the heading and updates `aria-live`. The layout is designed for a narrow screen and uses no external fonts.

## Prototype checks

| Action | Expected behaviour |
|---|---|
| Open the file | Only the form is visible; no time is selected |
| Confirm without choosing a time | The form stays open and the browser requires a selection |
| Select the first slot and confirm | Confirmation shows the selected time |
| Cancel | The cancellation state is visible; the previous slot is cleared |
| Register again and choose the second slot | Confirmation shows the new slot |
| Reload the page | The state resets; registration has not been saved |
| Navigate with the keyboard and use a narrow window | Fields are reachable and buttons and text fit |

This is a technical checking scenario. **No research with real users has been conducted.** It does not establish that the interface improved conversion, passed a complete accessibility audit or meets the requirements of a real registration service.

The next step after the hackathon is to observe how participants understand confirmation and cancellation, then check a real consent and storage process. This example deliberately contains no real personal data or external actions.
