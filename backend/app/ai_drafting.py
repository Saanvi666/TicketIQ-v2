import json
import os
from urllib import error, request

from .models import Ticket


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-4o-mini"


class EmailConfigurationError(RuntimeError):
    pass


class EmailGenerationError(RuntimeError):
    pass


def generate_resolution_email(
    ticket: Ticket,
    conversation: list[dict[str, str]],
) -> str:
    """Generate a customer-facing resolution email using OpenRouter."""

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise EmailConfigurationError(
            "OPENROUTER_API_KEY is not configured"
        )

    ticket_context = {
        "customer_name": ticket.customer_name,
        "subject": ticket.subject,
        "original_request": ticket.message,
        "conversation": conversation,
    }

    system_prompt = """
You are a professional customer-support representative writing a
customer-facing resolution email for TicketIQ.

Write a polished, natural and professional email based ONLY on the
customer's original request and conversation history.

Follow these rules strictly:

1. Start with a natural greeting using the customer's name when available.

2. Write 1–2 meaningful paragraphs. Do not make the email excessively short
   or reduce it to only one or two sentences.

3. Clearly explain that the reported issue has been addressed, using only
   information supported by the supplied customer request and conversation.

4. Refer naturally to the customer's actual issue rather than using vague
   phrases such as "your concern has been handled."

5. Do NOT invent:
   - refunds
   - replacements
   - technical actions
   - troubleshooting steps
   - policies
   - guarantees
   - compensation
   - timelines
   - investigations
   - actions performed by the support team
   unless they are explicitly supported by the supplied information.

6. Do not mention internal TicketIQ information, including:
   - ticket IDs
   - AI
   - classification
   - confidence
   - similarity
   - priority
   - routing
   - assigned team
   - agent review
   - internal status

7. Ask the customer to reply to the same email to confirm whether the issue
   has been resolved for them.

8. Clearly explain that:
   - they can reply "YES" if the issue is resolved
   - they can reply "NO" if the issue is still unresolved

9. Make the YES/NO instruction sound natural rather than like a website
   button or automated form.

10. Do not include links, URLs, buttons, HTML, markdown formatting,
    bullet-point lists, or a subject line.

11. Keep the tone warm, professional and reassuring without making
    unsupported promises.

12. End with:

Regards,
TicketIQ Support

13. Return ONLY the email body.
"""

    payload = {
        "model": OPENROUTER_MODEL,
        "temperature": 0.4,
        "max_tokens": 350,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Customer context:\n"
                    + json.dumps(
                        ticket_context,
                        ensure_ascii=True,
                    )
                    + "\n\nWrite the final customer-facing "
                      "resolution email."
                ),
            },
        ],
    }

    http_request = request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "TicketIQ",
        },
        method="POST",
    )

    try:
        with request.urlopen(
            http_request,
            timeout=30,
        ) as response:
            response_data = json.loads(
                response.read().decode("utf-8")
            )

    except error.HTTPError as exc:
        raise EmailGenerationError(
            f"OpenRouter returned HTTP {exc.code}"
        ) from exc

    except (
        error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        raise EmailGenerationError(
            "OpenRouter request failed"
        ) from exc

    try:
        draft = (
            response_data["choices"][0]["message"]["content"]
            .strip()
        )

    except (
        KeyError,
        IndexError,
        TypeError,
        AttributeError,
    ) as exc:
        raise EmailGenerationError(
            "OpenRouter returned an invalid response"
        ) from exc

    if not draft:
        raise EmailGenerationError(
            "OpenRouter returned an empty email"
        )

    return draft