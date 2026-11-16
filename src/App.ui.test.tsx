import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'

beforeEach(() => {
  // jsdom keeps location across tests — always start from the dashboard route
  window.location.hash = '#/'
})

describe('UI: navigation and core flows', () => {
  it('navigates between all main screens via the sidebar', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Shift & readings' }))
    expect(screen.getByRole('heading', { name: 'Shift & meter readings' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: 'Fuel & stock' }))
    expect(screen.getByRole('heading', { name: 'Fuel & stock' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: 'Credit ledger' }))
    expect(screen.getByRole('heading', { name: 'Credit ledger' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: 'Reports' }))
    expect(screen.getByRole('heading', { name: 'Reports' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }))
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Station overview')
  })

  it('shows empty states and sign-in guidance when no data is loaded', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Shift & readings' }))

    expect(await screen.findByText(/Not signed in:/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Petrol P1 opening (L)')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Close shift' })).toBeDisabled()
  })

  it('has an accessible main region, labeled controls and a station profile', () => {
    render(<App />)
    expect(screen.getAllByRole('main').length).toBeGreaterThanOrEqual(1)
    for (const name of [
      'Dashboard',
      'Shift & readings',
      'Fuel & stock',
      'Credit ledger',
      'Reports',
    ]) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument()
    }
    expect(screen.getByText('DeepBNK Station')).toBeInTheDocument()
    expect(screen.getByText('OB-001')).toBeInTheDocument()
    expect(screen.getByText('Melkote, Karnataka')).toBeInTheDocument()
  })

  it('shows the DeepBNK brand and offline status when not signed in', () => {
    render(<App />)
    expect(screen.getAllByText('DeepBNK').length).toBeGreaterThan(0)
    expect(screen.getByText('● Offline')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  })
})
