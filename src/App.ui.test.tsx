import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'

beforeEach(() => {
  // jsdom keeps location across tests — always start from the dashboard route
  window.location.hash = '#/'
})

describe('UI: navigation and core flows (demo mode)', () => {
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
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      /Good (morning|afternoon|evening), Deep/,
    )
  })

  it('shows an inline validation error when closing is below opening', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Shift & readings' }))
    fireEvent.change(await screen.findByLabelText('Petrol P1 opening (L)'), {
      target: { value: '12450' },
    })
    const closing = screen.getByLabelText('Petrol P1 closing (L)')
    fireEvent.change(closing, { target: { value: '12000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Validate readings' }))
    expect(await screen.findByText(/closing is below opening/i)).toBeInTheDocument()
    expect(closing).toHaveAttribute('aria-invalid', 'true')
  })

  it('has an accessible main region and labeled form controls', async () => {
    render(<App />)
    expect(screen.getAllByRole('main').length).toBeGreaterThanOrEqual(1)
    // every nav link and the station-settings link have accessible names
    for (const name of [
      'Dashboard',
      'Shift & readings',
      'Fuel & stock',
      'Credit ledger',
      'Reports',
    ]) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('link', { name: 'Shift & readings' }))
    expect(await screen.findByLabelText('Petrol P1 opening (L)')).toBeInTheDocument()
    expect(screen.getAllByText(/Server price ₹102.50\/L/).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Close shift' })).toBeInTheDocument()
  })

  it('shows clearly-labeled demo data when not signed in', () => {
    render(<App />)
    expect(screen.getAllByText(/Demo data:/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  })
})
