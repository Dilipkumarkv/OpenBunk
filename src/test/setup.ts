import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// render() accumulates into document.body when globals are disabled —
// unmount after every test so queries never see duplicate screens.
afterEach(() => {
  cleanup()
})
