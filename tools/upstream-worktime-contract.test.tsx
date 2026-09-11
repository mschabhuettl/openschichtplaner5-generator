// Copy into isolated OSP5 frontend/src/__tests__; synthetic mocked API only.
import { render, screen, fireEvent, waitFor, cleanup, act } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { vi, it, expect, beforeEach, afterEach } from 'vitest';
import WorkTimeRules from '../pages/WorkTimeRules';
import { api } from '../api/client';

vi.mock('../api/client', () => ({ api: {
  getWorkTimeRules: vi.fn(), getEmployees: vi.fn(), getGroups: vi.fn(),
  checkWorkTimeRules: vi.fn(), checkAllWorkTimeRules: vi.fn(),
} }));

const answer = (params: {plan?: 'ist' | 'soll'; from: string; to: string}) => ({
  violations: [], summary: {total: 0, warnings: 0, errors: 0},
  coverage: {contract: 'work-time-diagnostic-v1', plan: params.plan!,
    from: params.from, to: params.to, complete: false, reasons: ['timezone_unresolved']},
});
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getWorkTimeRules).mockResolvedValue({max_hours_per_day: 10,
    max_hours_per_week: 48, min_rest_hours_between_shifts: 11,
    max_consecutive_days: 6, enabled: true});
  vi.mocked(api.getEmployees).mockResolvedValue([{ID: 1, NAME: 'Synthetic', FIRSTNAME: 'A'}] as never);
  vi.mocked(api.getGroups).mockResolvedValue([]);
  vi.mocked(api.checkWorkTimeRules).mockImplementation(async p => answer(p));
  vi.mocked(api.checkAllWorkTimeRules).mockImplementation(async p => answer(p));
  render(<WorkTimeRules role="Planer" />);
});
afterEach(cleanup);
async function run() {
  const select = await screen.findByLabelText('Mitarbeiter auswählen') as HTMLSelectElement;
  await waitFor(() => expect(select.options.length).toBe(2));
  fireEvent.change(select, {target: {value: '1'}});
  fireEvent.click(screen.getByLabelText('Mitarbeiter prüfen'));
}
it('sends explicit Ist without inventing override limits; no green all-clear', async () => {
  await run();
  await screen.findByText(/Keine Auffälligkeiten im begrenzten Prüfumfang gefunden/);
  expect(api.checkWorkTimeRules).toHaveBeenCalledWith(expect.objectContaining({plan: 'ist'}));
  expect(vi.mocked(api.checkWorkTimeRules).mock.calls[0][0]).not.toHaveProperty('max_hours_per_week');
  expect(screen.queryByText(/✅ Keine Verstöße/)).toBeNull();
});
it('rejects legacy API responses without the selected-plan contract', async () => {
  vi.mocked(api.checkWorkTimeRules).mockResolvedValue({violations: [], summary: {total: 0, warnings: 0, errors: 0}});
  await run();
  await screen.findByText(/API bestätigt die angeforderte Plansicht\/Periode nicht/);
  expect(screen.queryByText(/Keine Auffälligkeiten im begrenzten Prüfumfang gefunden/)).toBeNull();
});
it('clears previous result and sends Soll on selection change', async () => {
  await run();
  await screen.findByText(/Keine Auffälligkeiten im begrenzten Prüfumfang gefunden/);
  fireEvent.change(screen.getByLabelText('Plansicht der Arbeitszeitdiagnose'), {target: {value: 'soll'}});
  expect(screen.queryByText(/Keine Auffälligkeiten im begrenzten Prüfumfang gefunden/)).toBeNull();
  await run();
  await waitFor(() => expect(api.checkWorkTimeRules).toHaveBeenLastCalledWith(expect.objectContaining({plan: 'soll'})));
});
it('locks plan selection until the pending request finishes', async () => {
  let resolve!: (value: ReturnType<typeof answer>) => void;
  vi.mocked(api.checkWorkTimeRules).mockImplementation(() => new Promise(r => {resolve = r;}));
  await run();
  expect(screen.getByLabelText('Plansicht der Arbeitszeitdiagnose')).toBeDisabled();
  await act(async () => resolve(answer(vi.mocked(api.checkWorkTimeRules).mock.calls[0][0])));
  await waitFor(() => expect(screen.getByLabelText('Plansicht der Arbeitszeitdiagnose')).not.toBeDisabled());
});
it('uses the same explicit contract for the group check', async () => {
  fireEvent.click(screen.getByLabelText('Alle prüfen'));
  await screen.findByText(/kein Nachweis vollständiger Regelkonformität/);
  expect(api.checkAllWorkTimeRules).toHaveBeenCalledWith(expect.objectContaining({plan: 'ist'}));
});
it('rejects an API response for the wrong requested period', async () => {
  vi.mocked(api.checkWorkTimeRules).mockImplementation(async p => answer({...p, from: '1900-01-01'}));
  await run();
  await screen.findByText(/API bestätigt die angeforderte Plansicht\/Periode nicht/);
});
it('clears the previous result when the requested period changes', async () => {
  await run();
  await screen.findByText(/Keine Auffälligkeiten im begrenzten Prüfumfang gefunden/);
  fireEvent.change(screen.getByLabelText('Startdatum'), {target: {value: '2026-01-01'}});
  expect(screen.queryByText(/Keine Auffälligkeiten im begrenzten Prüfumfang gefunden/)).toBeNull();
});
