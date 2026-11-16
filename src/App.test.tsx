import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the dashboard route with navigation', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      /Good (morning|afternoon|evening), Deep/,
    )
    expect(screen.getByRole('link', { name: /Shift & readings/i })).toHaveAttribute(
      'href',
      '#/shifts',
    )
  })
})
