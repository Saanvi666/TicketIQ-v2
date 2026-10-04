const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
).replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const payload = await response.json()
      detail = payload.detail || detail
    } catch {
      // Keep the status-based message when the server does not return JSON.
    }
    throw new Error(detail)
  }

  return response.status === 204 ? null : response.json()
}

export const api = {
  baseUrl: API_BASE_URL,
  getTickets: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value)).toString()
    return request(`/tickets${query ? `?${query}` : ''}`)
  },
  getHealth: () => request('/health'),
  getGmailProfile: () => request('/gmail/profile'),
  syncGmail: ({ maxResults = 25 } = {}) =>
    request(`/gmail/sync?confirm=true&max_results=${maxResults}`, {
      method: 'POST',
    }),
  resolveTicket: (ticketId) =>
    request(`/tickets/${ticketId}/resolve`, {
      method: 'POST',
    }),
  confirmClassification: (ticketId, classification) =>
    request(`/tickets/${ticketId}/classification`, {
      method: 'PUT',
      body: JSON.stringify(classification),
    }),
  decideCustomerReply: (ticketId, status) =>
    request(`/tickets/${ticketId}/customer-reply-decision`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
}
