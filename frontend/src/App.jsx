import {
  AlertCircle, AlertTriangle, ArrowLeft, Bot, Check, CheckCircle2, ChevronDown, Clock3,
  FileText, Inbox, LayoutDashboard, Menu, MessageSquareText, RefreshCw,
  Search, Ticket, Users, X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import './App.css'

const STATUS_ORDER = ['New', 'Assigned', 'In Progress', 'Resolved', 'Awaiting Customer', 'Reopened', 'Closed']
const DASHBOARD_STATUSES = ['New', 'In Progress', 'Awaiting Customer', 'Reopened', 'Closed']
const CATEGORIES = [
  'Account, Security & Login',
  'App, Website & Feedback',
  'Order Modifications & Cancellations',
  'Payment & Invoicing',
  'Product, Warranty & Tech Specs',
  'Returns, Refunds & Exchanges',
  'Shipping & Delivery'
]
const PRIORITIES = ['Urgent', 'High', 'Medium', 'Low']

function navigate(path) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function getRoute() {
  const path = window.location.pathname.replace(/\/$/, '') || '/dashboard'

  if (path === '/') return { page: 'dashboard' }
  if (path === '/tickets') return { page: 'tickets' }

  if (path.startsWith('/tickets/')) {
    return {
      page: 'details',
      ticketId: decodeURIComponent(path.split('/')[2]),
    }
  }

  return { page: 'dashboard' }
}

function App() {
  const [route, setRoute] = useState(getRoute)
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState(null)
  const [mobileNav, setMobileNav] = useState(false)

  useEffect(() => {
    const onPopState = () => setRoute(getRoute())

    window.addEventListener('popstate', onPopState)

    if (window.location.pathname === '/') {
      navigate('/dashboard')
    }

    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const loadTickets = async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)

    setError('')

    try {
      setTickets(await api.getTickets())
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true

    api.getTickets()
      .then((loadedTickets) => {
        if (active) setTickets(loadedTickets)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  const syncEmails = async () => {
    setSyncing(true)
    setSyncMessage(null)

    try {
      const result = await api.syncGmail()

      setSyncMessage({
        type: 'success',
        text: `${result.created ?? 0} new tickets synced.`,
      })

      await loadTickets()
    } catch (requestError) {
      setSyncMessage({
        type: 'error',
        text: requestError.message,
      })
    } finally {
      setSyncing(false)
    }
  }

  const closeMobileNav = () => setMobileNav(false)

  const apiConnectionLabel = error
    ? 'API unavailable'
    : loading
      ? 'Connecting...'
      : 'API connected'

  const content =
    route.page === 'details'
      ? loading
        ? <LoadingRows count={8} />
        : (
          <TicketDetails
            key={route.ticketId}
            ticket={tickets.find((ticket) => ticket.ticket_id === route.ticketId)}
            ticketsLoading={false}
            error={error}
            onRefresh={() => loadTickets({ silent: true })}
          />
        )
      : route.page === 'tickets'
        ? (
          <TicketsPage
            tickets={tickets}
            loading={loading}
            error={error}
            onRefresh={loadTickets}
            onSync={syncEmails}
            syncing={syncing}
            syncMessage={syncMessage}
          />
        )
        : (
          <Dashboard
            tickets={tickets}
            loading={loading}
            error={error}
            onSync={syncEmails}
            syncing={syncing}
          />
        )

  return (
    <div className="app-shell">
      <Sidebar
        page={route.page}
        mobileOpen={mobileNav}
        onNavigate={(path) => {
          navigate(path)
          closeMobileNav()
        }}
        onClose={closeMobileNav}
      />

      {mobileNav && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={closeMobileNav}
        />
      )}

      <main className="main-panel">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMobileNav(true)}
          >
            <Menu size={20} />
          </button>

          <div className="breadcrumbs">
            <span>Workspace</span>
            <span>/</span>
            <strong>
              {route.page === 'details'
                ? 'Ticket details'
                : route.page === 'tickets'
                  ? 'Tickets'
                  : 'Dashboard'}
            </strong>
          </div>

          <div
            className={`connection-status ${
              error ? 'disconnected' : loading ? 'checking' : ''
            }`}
            aria-live="polite"
          >
            <span className="status-dot" />
            {apiConnectionLabel}
          </div>
        </header>

        <div className="content-area">
          {content}
        </div>
      </main>
    </div>
  )
}

function Sidebar({ page, mobileOpen, onNavigate, onClose }) {
  return (
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand-lockup">
        <div className="brand-mark">
          <Ticket size={18} />
        </div>

        <div>
          <strong>TicketIQ</strong>
          <small>Support operations</small>
        </div>

        <button
          className="icon-button sidebar-close"
          onClick={onClose}
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>

      <p className="sidebar-label">Workspace</p>

      <nav className="primary-nav" aria-label="Primary navigation">
        <NavItem
          icon={LayoutDashboard}
          label="Dashboard"
          active={page === 'dashboard'}
          onClick={() => onNavigate('/dashboard')}
        />

        <NavItem
          icon={Inbox}
          label="Tickets"
          active={page === 'tickets' || page === 'details'}
          onClick={() => onNavigate('/tickets')}
        />
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-title">
          <Users size={16} />
          Agent workspace
        </div>

        <p>Keep every customer conversation moving.</p>

        <span className="environment-pill">
          <span />
          Local environment
        </span>
      </div>
    </aside>
  )
}

function NavItem({ icon: Icon, label, active, onClick }) {
  return (
    <button
      className={`nav-item ${active ? 'active' : ''}`}
      onClick={onClick}
    >
      <Icon size={17} />
      <span>{label}</span>
      {active && <span className="nav-active-bar" />}
    </button>
  )
}

function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>

      {action}
    </div>
  )
}

function Dashboard({ tickets, loading, error, onSync, syncing }) {
  const categoryCounts = CATEGORIES.map((category) => ({
    label: category,
    count: tickets.filter(
      (ticket) => (ticket.category || ticket.ai_category) === category
    ).length,
  }))

  const unclassifiedCount = tickets.filter(
    (ticket) => !ticket.category && !ticket.ai_category
  ).length

  if (unclassifiedCount) {
    categoryCounts.push({
      label: 'Unclassified',
      count: unclassifiedCount,
    })
  }

  const priorityCounts = PRIORITIES.map((priority) => ({
    label: priority,
    count: tickets.filter(
      (ticket) => (ticket.priority || ticket.ai_priority) === priority
    ).length,
  }))

  const statusCounts = STATUS_ORDER.map((status) => ({
    label: status,
    count: tickets.filter((ticket) => ticket.status === status).length,
  }))

  return (
    <>
      <PageHeader
        eyebrow="Support overview"
        title="Ticket dashboard"
        description="Live counts across the current support queue."
        action={
          <button
            className="primary-button"
            onClick={onSync}
            disabled={syncing}
          >
            <RefreshCw
              size={17}
              className={syncing ? 'spin' : ''}
            />
            {syncing ? 'Syncing...' : 'Sync emails'}
          </button>
        }
      />

      {error && <ErrorState message={error} />}

      <section
        className="summary-grid dashboard-status-grid"
        aria-label="Ticket status counts"
      >
        {DASHBOARD_STATUSES.map((status) => (
          <SummaryCard
            key={status}
            status={status}
            count={
              loading
                ? null
                : tickets.filter((ticket) => ticket.status === status).length
            }
          />
        ))}
      </section>

      <div className="analytics-grid">
        <ChartPanel
          title="Issues by category"
          description="Final category, or AI prediction while review is pending."
          loading={loading}
        >
          <CountChart
            items={categoryCounts}
            color="category"
          />
        </ChartPanel>

        <ChartPanel
          title="Priority analysis"
          description="Final priority, or AI prediction while review is pending."
          loading={loading}
        >
          <CountChart
            items={priorityCounts}
            color="priority"
          />
        </ChartPanel>

        <ChartPanel
          title="Ticket status distribution"
          description={`${tickets.length} total ${
            tickets.length === 1 ? 'ticket' : 'tickets'
          }.`}
          loading={loading}
        >
          <StatusDistribution
            items={statusCounts}
            total={tickets.length}
          />
        </ChartPanel>
      </div>
    </>
  )
}

function SummaryCard({ status, count }) {
  const icons = {
    New: Inbox,
    'In Progress': Clock3,
    'Awaiting Customer': MessageSquareText,
    Reopened: RefreshCw,
    Closed: Check,
  }

  const Icon = icons[status] || FileText

  return (
    <div
      className={`summary-card summary-${status
        .toLowerCase()
        .replaceAll(' ', '-')}`}
    >
      <div className="summary-icon">
        <Icon size={20} />
      </div>

      <div>
        <strong>{count === null ? '—' : count}</strong>
        <span>{status}</span>
      </div>
    </div>
  )
}

function ChartPanel({ title, description, loading, children }) {
  return (
    <section className="panel chart-panel">
      <div className="chart-heading">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      {loading ? <LoadingRows count={4} /> : children}
    </section>
  )
}

function CountChart({ items, color }) {
  if (!items.some((item) => item.count > 0)) {
    return (
      <EmptyState
        message={
          color === 'category'
            ? 'No category data yet.'
            : 'No priority data yet.'
        }
      />
    )
  }

  const max = Math.max(
    ...items.map((item) => item.count),
    1
  )

  return (
    <div className="count-chart">
      {items.map((item, index) => (
        <div
          className="chart-row"
          key={item.label}
        >
          <span className="chart-label">
            {item.label}
          </span>

          <div
            className={`chart-track ${color} ${color}-${item.label
              .toLowerCase()
              .replaceAll(/[^a-z]+/g, '-')}`}
          >
            <span
              style={{
                width: `${
                  item.count
                    ? Math.max((item.count / max) * 100, 2)
                    : 0
                }%`,
                '--bar-index': index,
              }}
            />
          </div>

          <strong className="chart-count">
            {item.count}
          </strong>
        </div>
      ))}
    </div>
  )
}

function StatusDistribution({ items, total }) {
  const activeItems = items.filter(
    (item) => item.count > 0
  )

  if (!total) {
    return <EmptyState message="No ticket activity yet." />
  }

  return (
    <div className="status-chart">
      <div
        className="status-strip"
        role="img"
        aria-label={activeItems
          .map((item) => `${item.label}: ${item.count}`)
          .join(', ')}
      >
        {activeItems.map((item) => (
          <span
            key={item.label}
            className={`status-segment segment-${item.label
              .toLowerCase()
              .replaceAll(' ', '-')}`}
            style={{
              width: `${(item.count / total) * 100}%`,
            }}
            title={`${item.label}: ${item.count}`}
          />
        ))}
      </div>

      <div className="status-legend">
        {items.map((item) => (
          <div
            className="legend-item"
            key={item.label}
          >
            <span
              className={`legend-swatch segment-${item.label
                .toLowerCase()
                .replaceAll(' ', '-')}`}
            />

            <span>{item.label}</span>

            <strong>{item.count}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

function TicketsPage({
  tickets,
  loading,
  error,
  onRefresh,
  onSync,
  syncing,
  syncMessage,
}) {
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({
    status: '',
    category: '',
    priority: '',
  })

  const visibleTickets = useMemo(
    () =>
      tickets.filter((ticket) => {
        const query = search.toLowerCase()

        const matchesSearch =
          !query ||
          [
            ticket.ticket_id,
            ticket.customer_name,
            ticket.customer_email,
            ticket.subject,
          ].some((value) =>
            value?.toLowerCase().includes(query)
          )

        return (
          matchesSearch &&
          (!filters.status ||
            ticket.status === filters.status) &&
          (!filters.category ||
            (ticket.category || ticket.ai_category) ===
              filters.category) &&
          (!filters.priority ||
            (ticket.priority || ticket.ai_priority) ===
              filters.priority)
        )
      }),
    [tickets, search, filters]
  )

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Tickets"
        description="A focused view of customer requests."
        action={
          <div className="header-actions">
            <button
              className="secondary-button"
              onClick={onRefresh}
            >
              <RefreshCw size={17} />
              Refresh
            </button>

            <button
              className="primary-button"
              onClick={onSync}
              disabled={syncing}
            >
              <RefreshCw
                size={17}
                className={syncing ? 'spin' : ''}
              />
              {syncing ? 'Syncing...' : 'Sync emails'}
            </button>
          </div>
        }
      />

      {syncMessage && (
        <Notice
          type={syncMessage.type}
          message={syncMessage.text}
        />
      )}

      {error && <ErrorState message={error} />}

      <section className="panel table-panel">
        <div className="table-toolbar">
          <label className="search-box">
            <Search size={19} />

            <input
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search ticket ID, subject, or customer"
            />
          </label>

          <div className="filter-row">
            <FilterSelect
              label="Category"
              value={filters.category}
              options={CATEGORIES}
              onChange={(value) =>
                setFilters({
                  ...filters,
                  category: value,
                })
              }
            />

            <FilterSelect
              label="Priority"
              value={filters.priority}
              options={PRIORITIES}
              onChange={(value) =>
                setFilters({
                  ...filters,
                  priority: value,
                })
              }
            />

            <FilterSelect
              label="Status"
              value={filters.status}
              options={Array.from(
                new Set(
                  tickets
                    .map((ticket) => ticket.status)
                    .filter(Boolean)
                )
              )}
              onChange={(value) =>
                setFilters({
                  ...filters,
                  status: value,
                })
              }
            />
          </div>
        </div>

        {loading ? (
          <LoadingRows count={6} />
        ) : visibleTickets.length ? (
          <TicketTable tickets={visibleTickets} />
        ) : (
          <EmptyState
            message={
              tickets.length
                ? 'No tickets match these filters.'
                : 'No tickets have been synced yet.'
            }
            action={tickets.length ? null : onSync}
            actionLabel="Sync emails"
          />
        )}
      </section>
    </>
  )
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}) {
  return (
    <label className="filter-select">
      <span>{label}</span>

      <select
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
      >
        <option value="">All</option>

        {options.map((option) => (
          <option
            key={option}
            value={option}
          >
            {option}
          </option>
        ))}
      </select>

      <ChevronDown size={14} />
    </label>
  )
}

function TicketTable({ tickets }) {
  return (
    <div className="ticket-table-wrap">
      <table className="ticket-table">
        <thead>
          <tr>
            <th>Ticket ID</th>
            <th>Subject</th>
            <th>Category</th>
            <th>Priority</th>
            <th>Status</th>
          </tr>
        </thead>

        <tbody>
          {tickets.map((ticket) => (
            <TicketRow
              key={ticket.ticket_id}
              ticket={ticket}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TicketRow({ ticket }) {
  const category =
    ticket.category || ticket.ai_category

  const predictedCategory =
    !ticket.category &&
    Boolean(ticket.ai_category)

  const closed = ticket.status === 'Closed'

  return (
    <tr
      className={
        closed
          ? 'ticket-row-closed'
          : `ticket-row-${ticket.status
              .toLowerCase()
              .replaceAll(' ', '-')}`
      }
      role="link"
      tabIndex={0}
      aria-label={`Open ${ticket.status} ticket ${ticket.ticket_id}: ${ticket.subject}`}
      onClick={() =>
        navigate(
          `/tickets/${encodeURIComponent(
            ticket.ticket_id
          )}`
        )
      }
      onKeyDown={(event) => {
        if (
          event.key === 'Enter' ||
          event.key === ' '
        ) {
          event.preventDefault()

          navigate(
            `/tickets/${encodeURIComponent(
              ticket.ticket_id
            )}`
          )
        }
      }}
    >
      <td>
        <span
          className={`ticket-link ${
            closed ? 'closed-value' : ''
          }`}
        >
          {ticket.ticket_id}
        </span>
      </td>

      <td className="subject-cell">
        <strong
          className={closed ? 'closed-value' : ''}
        >
          {ticket.subject}
        </strong>
      </td>

      <td>
        <CategoryBadge
          category={category}
          predicted={predictedCategory}
          crossedOut={closed}
        />
      </td>

      <td>
        <PriorityBadge
          priority={
            ticket.priority || ticket.ai_priority
          }
          labelPrefix={
            ticket.priority ? '' : 'AI · '
          }
        />
      </td>

      <td>
        <StatusBadge status={ticket.status} />
      </td>
    </tr>
  )
}

function TicketDetails({
  ticket,
  ticketsLoading,
  error,
  onRefresh,
}) {
  const [resolveLoading, setResolveLoading] =
    useState(false)

  const [resolveNotice, setResolveNotice] =
    useState(null)

  const [localStatus, setLocalStatus] =
    useState('')

  const [reviewCategory, setReviewCategory] =
    useState(
      ticket?.ai_category ||
        ticket?.category ||
        CATEGORIES[0]
    )

  const [reviewPriority, setReviewPriority] =
    useState(
      ticket?.ai_priority ||
        ticket?.priority ||
        'Medium'
    )

  const [reviewLoading, setReviewLoading] =
    useState(false)

  const [reviewNotice, setReviewNotice] =
    useState(null)

  const [reviewOpen, setReviewOpen] =
    useState(false)

  const [
    replyDecisionLoading,
    setReplyDecisionLoading,
  ] = useState(false)

  if (ticketsLoading) {
    return <LoadingRows count={8} />
  }

  if (error) {
    return <ErrorState message={error} />
  }

  if (!ticket) {
    return (
      <EmptyState
        message="Ticket not found."
        action={() => navigate('/tickets')}
        actionLabel="Back to tickets"
      />
    )
  }

  const status = localStatus || ticket.status

  // Keep the working classification confirmation behavior.
  const agentConfirmed =
    ticket.review_status === 'agent_confirmed' ||
    Boolean(ticket.category && ticket.priority)

  const requiresReview =
    !agentConfirmed &&
    (
      [
        'review_required',
        'agent_review_required',
      ].includes(ticket.review_status) ||
      Boolean(
        ticket.ai_category &&
        (!ticket.category || !ticket.priority)
      )
    )

  const canResolve =
    !requiresReview &&
    status !== 'Awaiting Customer' &&
    status !== 'Closed' &&
    (
      status !== 'Resolved' ||
      Boolean(ticket.resolution_email_error)
    )

  const resolve = async () => {
    setResolveLoading(true)
    setResolveNotice(null)

    try {
      const result =
        await api.resolveTicket(
          ticket.ticket_id
        )

      setLocalStatus(result.status)

      setResolveNotice(
        result.resolution_email_sent
          ? {
              type: 'success',
              text: 'Resolution email sent. The ticket is awaiting the customer.',
            }
          : {
              type: 'error',
              text:
                result.resolution_email_error ||
                'The resolution email was not sent.',
            }
      )

      await onRefresh()
    } catch (requestError) {
      setResolveNotice({
        type: 'error',
        text: requestError.message,
      })
    } finally {
      setResolveLoading(false)
    }
  }

  const confirmReview = async () => {
    setReviewLoading(true)
    setReviewNotice(null)

    try {
      await api.confirmClassification(
        ticket.ticket_id,
        {
          category: reviewCategory,
          priority: reviewPriority,
        }
      )

      setReviewOpen(false)

      setReviewNotice({
        type: 'success',
        text: 'Agent classification confirmed.',
      })

      await onRefresh()
    } catch (requestError) {
      setReviewNotice({
        type: 'error',
        text: requestError.message,
      })
    } finally {
      setReviewLoading(false)
    }
  }

  const decideCustomerReply = async (decision) => {
    setReplyDecisionLoading(true)
    setResolveNotice(null)

    try {
      const result =
        await api.decideCustomerReply(
          ticket.ticket_id,
          decision
        )

      setLocalStatus(result.status)

      await onRefresh()
    } catch (requestError) {
      setResolveNotice({
        type: 'error',
        text: requestError.message,
      })
    } finally {
      setReplyDecisionLoading(false)
    }
  }

  const statusInfo =
    getTicketStatusInfo(
      ticket,
      status
    )

  const storedMessages =
    ticket.conversation_messages || []

  const originalMessagePresent =
    storedMessages.some(
      (message) =>
        ['incoming', 'customer'].includes(
          message.direction?.toLowerCase()
        ) &&
        message.body === ticket.message
    )

  const conversationMessages =
    originalMessagePresent
      ? storedMessages
      : [
          {
            id: 'original',
            direction: 'incoming',
            body: ticket.message,
            sent_at: ticket.created_at,
          },
          ...storedMessages,
        ]

  return (
    <>
      <button
        className="back-button"
        onClick={() => navigate('/tickets')}
      >
        <ArrowLeft size={16} />
        Back to tickets
      </button>

      <header className="details-header">
        <div>
          <p className="ticket-id-label">
            {ticket.ticket_id}
          </p>

          <h1>{ticket.subject}</h1>

          <p className="page-description">
            Opened {formatDate(ticket.created_at)}
            <span aria-hidden="true"> · </span>
            {ticket.customer_name}
          </p>
        </div>
      </header>

      <div className="details-layout">
        {/* LEFT SIDE */}
        <div className="details-main">
          <InfoCard
            title="Customer Information"
            icon={Users}
          >
            <div className="customer-detail">
              <span className="large-avatar">
                {initials(ticket.customer_name)}
              </span>

              <div>
                <strong>
                  {ticket.customer_name}
                </strong>

                <a
                  href={`mailto:${ticket.customer_email}`}
                >
                  {ticket.customer_email}
                </a>
              </div>
            </div>
          </InfoCard>

          <InfoCard
            title="Customer Request"
            icon={MessageSquareText}
          >
            <div className="request-content">
              <strong>{ticket.subject}</strong>
              <p>{ticket.message}</p>
            </div>
          </InfoCard>

          <InfoCard
            title="Conversation History"
            icon={MessageSquareText}
            className="conversation-card"
          >
            <div className="conversation">
              {conversationMessages.map(
                (message) => {
                  const messageDirection =
                    message.direction?.toLowerCase()

                  const direction =
                    [
                      'incoming',
                      'customer',
                    ].includes(
                      messageDirection
                    )
                      ? 'incoming'
                      : [
                            'outgoing',
                            'agent',
                          ].includes(
                            messageDirection
                          )
                        ? 'outgoing'
                        : 'system'

                  const name =
                    direction === 'incoming'
                      ? ticket.customer_name
                      : direction === 'outgoing'
                        ? 'Agent'
                        : 'TicketIQ Support'

                  const role =
                    direction === 'incoming'
                      ? 'Customer'
                      : direction === 'outgoing'
                        ? 'Agent'
                        : 'System'

                  return (
                    <MessageBubble
                      key={
                        message.id ||
                        message.sent_at
                      }
                      direction={direction}
                      name={name}
                      role={role}
                      date={message.sent_at}
                      body={message.body}
                    />
                  )
                }
              )}
            </div>
          </InfoCard>
        </div>

        {/* RIGHT SIDE */}
        <aside className="details-side">
          <InfoCard
            title="Ticket Status"
            icon={statusInfo.Icon}
          >
            <div
              className={`ticket-status-card status-card-${status
                .toLowerCase()
                .replaceAll(' ', '-')}`}
            >
              <strong>
                {status.toUpperCase()}
              </strong>

              <p>{statusInfo.description}</p>
            </div>
          </InfoCard>

          {ticket.customer_reply_review_required && (
            <InfoCard
              title="Customer reply needs review"
              icon={AlertTriangle}
            >
              <p className="review-explanation">
                The customer's reply is ambiguous.
                Choose a status after reviewing the
                conversation in the main panel.
              </p>

              <div className="review-actions">
                <button
                  className="secondary-button"
                  onClick={() =>
                    decideCustomerReply(
                      'Reopened'
                    )
                  }
                  disabled={
                    replyDecisionLoading
                  }
                >
                  Reopen ticket
                </button>

                <button
                  className="primary-button"
                  onClick={() =>
                    decideCustomerReply(
                      'Closed'
                    )
                  }
                  disabled={
                    replyDecisionLoading
                  }
                >
                  Close ticket
                </button>
              </div>
            </InfoCard>
          )}

          <InfoCard
            title="AI Assessment & Agent Review"
            icon={Bot}
            className="assessment-card"
          >
            <div className="assessment-predictions">
              <div className="assessment-prediction">
                <span>
                  AI Predicted Category
                </span>

                <CategoryBadge
                  category={
                    ticket.ai_category ||
                    ticket.category
                  }
                />
              </div>

              <div className="assessment-prediction">
                <span>
                  AI Predicted Priority
                </span>

                <PriorityBadge
                  priority={
                    ticket.ai_priority ||
                    ticket.priority
                  }
                />
              </div>

              <div className="assessment-similarity">
                <span>AI Similarity</span>

                <strong>
                  {ticket.confidence == null
                    ? 'Not available'
                    : ticket.confidence.toFixed(
                        3
                      )}
                </strong>

                <small>
                  Cosine similarity score, not a
                  calibrated probability.
                </small>
              </div>
            </div>

            <ol
              className="assessment-flow"
              aria-label="AI prediction, similarity check, human review when required, and final classification"
            >
              <li>
                <strong>
                  AI prediction
                </strong>
              </li>

              <li>
                <strong>
                  Similarity check
                </strong>
              </li>

              <li
                className={
                  requiresReview
                    ? 'flow-review-required'
                    : ''
                }
              >
                <strong>
                  {requiresReview
                    ? 'Agent review required'
                    : agentConfirmed
                      ? 'Agent review completed'
                      : 'AI prediction accepted'}
                </strong>
              </li>

              <li>
                <strong>
                  Final classification
                </strong>
              </li>
            </ol>

            {requiresReview ? (
              <section className="agent-review-warning">
                <div className="review-warning-heading">
                  <AlertTriangle size={23} />
                  <h3>
                    AGENT REVIEW REQUIRED
                  </h3>
                </div>

                <p>
                  The AI classification requires
                  human confirmation before the
                  ticket can proceed.
                </p>

                {!reviewOpen ? (
                  <button
                    className="primary-button"
                    onClick={() =>
                      setReviewOpen(true)
                    }
                  >
                    Review &amp; Confirm
                  </button>
                ) : (
                  <div className="review-editor">
                    <label className="review-field">
                      Final Category

                      <select
                        value={reviewCategory}
                        onChange={(event) =>
                          setReviewCategory(
                            event.target.value
                          )
                        }
                      >
                        {CATEGORIES.map(
                          (category) => (
                            <option
                              key={category}
                              value={category}
                            >
                              {category}
                            </option>
                          )
                        )}
                      </select>
                    </label>

                    <label className="review-field">
                      Final Priority

                      <select
                        value={reviewPriority}
                        onChange={(event) =>
                          setReviewPriority(
                            event.target.value
                          )
                        }
                      >
                        {PRIORITIES.map(
                          (priority) => (
                            <option
                              key={priority}
                              value={priority}
                            >
                              {priority}
                            </option>
                          )
                        )}
                      </select>
                    </label>

                    <div className="review-editor-actions">
                      <button
                        className="secondary-button"
                        onClick={() =>
                          setReviewOpen(false)
                        }
                        disabled={
                          reviewLoading
                        }
                      >
                        Cancel
                      </button>

                      <button
                        className="primary-button"
                        onClick={confirmReview}
                        disabled={
                          reviewLoading
                        }
                      >
                        {reviewLoading
                          ? 'Saving...'
                          : 'Confirm Final Category & Priority'}
                      </button>
                    </div>
                  </div>
                )}

                {reviewNotice && (
                  <Notice
                    type={reviewNotice.type}
                    message={reviewNotice.text}
                  />
                )}
              </section>
            ) : (
              <div
                className={`assessment-accepted ${
                  agentConfirmed
                    ? 'agent-classification-confirmed'
                    : ''
                }`}
              >
                <CheckCircle2 size={20} />

                <strong>
                  {agentConfirmed
                    ? 'Agent classification confirmed'
                    : 'AI classification accepted'}
                </strong>

                <span>
                  {agentConfirmed
                    ? 'The agent confirmed the final category and priority.'
                    : 'Similarity meets the existing review threshold.'}
                </span>
              </div>
            )}
          </InfoCard>

          <InfoCard
            title="Final Classification"
            icon={Check}
          >
            <div className="final-classification-values">
              <div>
                <span>Final Category</span>

                {ticket.category ? (
                  <CategoryBadge
                    category={ticket.category}
                  />
                ) : (
                  <strong className="classification-pending">
                    Awaiting agent confirmation
                  </strong>
                )}
              </div>

              <div>
                <span>Final Priority</span>

                {ticket.priority ? (
                  <PriorityBadge
                    priority={ticket.priority}
                  />
                ) : (
                  <strong className="classification-pending">
                    Awaiting agent confirmation
                  </strong>
                )}
              </div>
            </div>
          </InfoCard>

          {/* MOVED HERE: Resolution Action is now in the RIGHT SIDEBAR */}
          <InfoCard
            title="Resolution Action"
            icon={Check}
          >
            <p className="resolution-action-copy">
              When the issue has been addressed, send a
              confirmation email to the customer. The
              ticket will await their response after
              successful delivery.
            </p>

            {resolveNotice && (
              <Notice
                type={resolveNotice.type}
                message={resolveNotice.text}
              />
            )}

            {canResolve ? (
              <button
                className="primary-button resolution-action-button"
                onClick={resolve}
                disabled={resolveLoading}
              >
                {resolveLoading
                  ? 'Sending resolution email...'
                  : 'Mark as Resolved'}
              </button>
            ) : (
              <p className="resolution-state-note">
                {status === 'Closed'
                  ? 'This ticket is closed.'
                  : status === 'Awaiting Customer'
                    ? 'The resolution email has been sent; the ticket is waiting for the customer.'
                    : status === 'Resolved'
                      ? 'The resolution email has already been sent.'
                      : 'Confirm the final category and priority before resolving.'}
              </p>
            )}

            {ticket.resolution_email_error && (
              <p className="resolution-error">
                Previous email attempt failed:{' '}
                {ticket.resolution_email_error}
              </p>
            )}
          </InfoCard>
        </aside>
      </div>
    </>
  )
}

function getTicketStatusInfo(ticket, status) {
  const messages =
    ticket.conversation_messages || []

  const latestSystemEvent =
    [...messages]
      .reverse()
      .find(
        (message) =>
          message.direction === 'system'
      )
      ?.body?.toLowerCase() || ''

  const latestCustomerMessage =
    customerReplyText(
      [...messages]
        .reverse()
        .find((message) =>
          [
            'incoming',
            'customer',
          ].includes(
            message.direction?.toLowerCase()
          )
        )?.body || ''
    )

  if (status === 'Closed') {
    if (
      latestSystemEvent.includes(
        'automatically closed'
      )
    ) {
      return {
        Icon: CheckCircle2,
        description:
          'Closed automatically after the customer response waiting period.',
      }
    }

    if (
      latestSystemEvent.includes(
        "customer selected 'yes, issue solved'"
      )
    ) {
      return {
        Icon: CheckCircle2,
        description:
          'Customer confirmed the issue was resolved.',
      }
    }

    if (
      latestSystemEvent.includes(
        'customer confirmed that the issue was resolved'
      )
    ) {
      return {
        Icon: CheckCircle2,
        description:
          'Customer confirmed the issue was resolved.',
      }
    }

    if (
      latestSystemEvent.includes(
        'agent reviewed the customer reply'
      )
    ) {
      return {
        Icon: CheckCircle2,
        description:
          'Agent reviewed the customer response and closed the ticket.',
      }
    }

    if (
      customerConfirmedResolution(
        latestCustomerMessage
      )
    ) {
      return {
        Icon: CheckCircle2,
        description:
          'Customer confirmed the issue was resolved.',
      }
    }

    return {
      Icon: CheckCircle2,
      description:
        'This ticket has been closed.',
    }
  }

  if (status === 'Reopened') {
    if (
      latestSystemEvent.includes(
        "customer selected 'no, issue not solved'"
      )
    ) {
      return {
        Icon: AlertTriangle,
        description:
          'Customer reported that the issue is still unresolved.',
      }
    }

    if (
      latestSystemEvent.includes(
        'customer reported that the issue is still unresolved'
      )
    ) {
      return {
        Icon: AlertTriangle,
        description:
          'Customer reported that the issue is still unresolved.',
      }
    }

    if (
      latestSystemEvent.includes(
        'agent reviewed the customer reply'
      )
    ) {
      return {
        Icon: AlertTriangle,
        description:
          'Agent reviewed the customer response and reopened the ticket.',
      }
    }

    if (
      customerReportedUnresolved(
        latestCustomerMessage
      )
    ) {
      return {
        Icon: AlertTriangle,
        description:
          'Customer reported that the issue is still unresolved.',
      }
    }

    return {
      Icon: AlertTriangle,
      description:
        'This ticket is reopened and ready for agent follow-up.',
    }
  }

  if (status === 'Awaiting Customer') {
    return {
      Icon: Clock3,
      description:
        "Waiting for the customer's resolution confirmation.",
    }
  }

  if (status === 'Resolved') {
    return {
      Icon: CheckCircle2,
      description: ticket.resolution_email_error
        ? 'The issue was marked resolved, but the customer email needs attention.'
        : 'The issue has been marked as resolved.',
    }
  }

  if (status === 'In Progress') {
    return {
      Icon: Clock3,
      description:
        'An agent is working on this customer request.',
    }
  }

  return {
    Icon: AlertCircle,
    description:
      'This ticket is awaiting agent review.',
  }
}

function customerConfirmedResolution(message) {
  if (customerReportedUnresolved(message)) {
    return false
  }

  return /\b(?:resolved|fixed|solved|working now|works now|all good now)\b/.test(
    message
  )
}

function customerReplyText(message) {
  return message
    .split(
      /(?:\r?\n)\s*(?:on .{1,240}?\bwrote:|[-_]{2,}\s*original message\s*[-_]{2,}|begin forwarded message:|from:\s*[^\r\n]+)/i,
      1
    )[0]
    .split(
      /\s+on .{1,240}?\bwrote:\s*/i,
      1
    )[0]
    .split(
      /(?:\r?\n)\s*>/,
      1
    )[0]
    .toLowerCase()
}

function customerReportedUnresolved(message) {
  return /\b(?:not resolved|isn't resolved|is not resolved|unresolved|not fixed|isn't fixed|is not fixed|not working|still broken|issue persists|still doesn't work|still does not work)\b/.test(
    message
  )
}

function InfoCard({
  title,
  icon: Icon,
  children,
  className = '',
}) {
  return (
    <section
      className={`panel info-card ${className}`}
    >
      <div className="info-card-heading">
        <Icon size={19} />
        <h2>{title}</h2>
      </div>

      {children}
    </section>
  )
}

function MessageBubble({
  direction,
  name,
  role,
  date,
  body,
}) {
  return (
    <article
      className={`message-bubble ${direction}`}
    >
      <div className="message-meta">
        <div>
          <strong>{name}</strong>
          <span className="message-role">
            {role}
          </span>
        </div>

        <time dateTime={date}>
          {formatDate(date)}
        </time>
      </div>

      <p>{body}</p>
    </article>
  )
}

function CategoryBadge({
  category,
  predicted = false,
  crossedOut = false,
}) {
  const categoryIndex =
    CATEGORIES.indexOf(category)

  return (
    <span
      className={`category-badge category-tone-${
        categoryIndex < 0
          ? 'neutral'
          : categoryIndex
      } ${
        crossedOut ? 'closed-value' : ''
      }`}
    >
      {category || 'Unclassified'}

      {predicted && (
        <small>AI prediction</small>
      )}
    </span>
  )
}

function PriorityBadge({
  priority,
  labelPrefix = '',
}) {
  return (
    <span
      className={`badge priority-${
        (priority || 'none').toLowerCase()
      }`}
    >
      <span />

      {priority
        ? `${labelPrefix}${priority}`
        : 'Unassigned'}
    </span>
  )
}

function StatusBadge({ status }) {
  return (
    <span
      className={`badge status-${
        (status || 'unknown')
          .toLowerCase()
          .replaceAll(' ', '-')
      }`}
    >
      {status || 'Unknown'}
    </span>
  )
}

function LoadingRows({ count = 4 }) {
  return (
    <div className="loading-list">
      {Array.from(
        { length: count },
        (_, index) => (
          <div
            className="skeleton-row"
            key={index}
          >
            <span />
            <span />
            <span />
            <span />
          </div>
        )
      )}
    </div>
  )
}

function EmptyState({
  message,
  action,
  actionLabel,
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <Inbox size={19} />
      </div>

      <strong>{message}</strong>

      {action && (
        <button
          className="secondary-button"
          onClick={action}
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}

function ErrorState({ message }) {
  return (
    <div className="error-state">
      <AlertCircle size={17} />
      <span>{message}</span>
    </div>
  )
}

function Notice({ type, message }) {
  return (
    <div className={`notice ${type}`}>
      {type === 'success' ? (
        <Check size={15} />
      ) : (
        <AlertCircle size={15} />
      )}

      {message}
    </div>
  )
}

function initials(name = '') {
  return (
    name
      .split(' ')
      .map((part) => part[0])
      .slice(0, 2)
      .join('')
      .toUpperCase() || '?'
  )
}

function formatDate(value) {
  if (!value) return 'Unknown date'

  return new Intl.DateTimeFormat(
    'en',
    {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }
  ).format(new Date(value))
}

export default App