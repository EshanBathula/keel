import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Forecast from './Forecast.jsx'

vi.mock('../lib/api.js', async () => {
  const actual = await vi.importActual('../lib/api.js')
  return { ...actual, api: vi.fn() }
})

import { api } from '../lib/api.js'

const baseForecast = {
  confidence: 'normal',
  model_revenue: 'damped_trend',
  model_expenses: 'ols_ma_blend',
  expected_error_pct: 18.4,
  weekly: [
    { week_start: '2026-07-13', cash_p10: 8000, cash_p50: 9000, cash_p90: 10000 },
    { week_start: '2026-07-20', cash_p10: 8200, cash_p50: 9400, cash_p90: 10600 },
  ],
  monthly: [
    { month: '2026-07', projected_revenue: 5000, projected_expenses: 2000, projected_net: 3000, lower: 4000, upper: 6000 },
  ],
  min_cash_balance: 8000,
  min_cash_balance_date: '2026-07-13',
  cash_low_alert: null,
  safe_to_spend: 3500,
  caveat: null,
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('Forecast page', () => {
  it('shows a loading state before data arrives', () => {
    api.mockReturnValue(new Promise(() => {})) // never resolves
    render(<Forecast />)
    expect(screen.getByText('Projecting…')).toBeInTheDocument()
  })

  it('renders an inline error if the forecast request fails', async () => {
    api.mockRejectedValue(new Error('Session expired'))
    render(<Forecast />)
    expect(await screen.findByText(/Couldn.t load the forecast/)).toBeInTheDocument()
    expect(screen.getByText(/Session expired/)).toBeInTheDocument()
  })

  it('renders headline numbers once loaded, with no caveat or alert', async () => {
    api.mockResolvedValue(baseForecast)
    render(<Forecast />)
    expect(await screen.findByText('$3,500')).toBeInTheDocument() // safe to spend
    expect(screen.getByText('$8,000')).toBeInTheDocument() // min balance
    expect(screen.getByText('±18.4%')).toBeInTheDocument()
    expect(screen.queryByText(/grain of salt/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Cash low warning/)).not.toBeInTheDocument()
  })

  it('shows the low-confidence caveat in plain language', async () => {
    api.mockResolvedValue({
      ...baseForecast,
      confidence: 'low',
      expected_error_pct: null,
      caveat: 'Less than 12 weeks of transaction history — this forecast is a rough estimate.',
    })
    render(<Forecast />)
    expect(await screen.findByText(/grain of salt/)).toBeInTheDocument()
    expect(screen.getByText(/Less than 12 weeks/)).toBeInTheDocument()
    // With no backtest, accuracy reads as an em dash, not a fabricated number.
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText(/Not enough history to backtest/)).toBeInTheDocument()
  })

  it('renders the cash-low alert with its date and shortfall', async () => {
    api.mockResolvedValue({
      ...baseForecast,
      cash_low_alert: { week_start: '2026-08-03', shortfall: 1250 },
    })
    render(<Forecast />)
    const alert = await screen.findByText(/Cash low warning/)
    expect(alert).toBeInTheDocument()
    const alertBlock = alert.closest('div')
    expect(alertBlock).toHaveTextContent('$1,250')
    expect(alertBlock).toHaveTextContent('Aug 3')
  })
})
