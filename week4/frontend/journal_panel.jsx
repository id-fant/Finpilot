// journal_panel.jsx — the agent's decision diary, rendered from
// /api/portfolio/journal/ (JournalEntry rows written by the analyst gate,
// the exit sweep and the trading-session supervisor).
//
// WHY this panel exists: the whole point of the agentic layer is that every
// decision is auditable — "why did it trade / refuse / exit?" This view makes
// that auditable WITHOUT opening the Django admin.
//
// Components exported on window:
//   JournalView — sidebar-nav wrapper (PageHead + polling table)

const { useState: jUseState } = React;

const JOURNAL_POLL_MS = 30_000;

const STAGE_FILTERS = ['all', 'ml', 'analyst', 'exit', 'execution', 'session', 'signal'];

// Decision word → colour. Green for go, red for stop, neutral otherwise.
function decisionColor(decision) {
  if (['APPROVE', 'START'].includes(decision)) return 'var(--green)';
  if (['VETO', 'SELL', 'REJECT'].includes(decision)) return 'var(--red)';
  if (decision === 'REDUCE') return 'var(--amber, #d97706)';
  return 'var(--text-2)';
}

function JournalView() {
  const [stage, setStage] = jUseState('all');
  const qs = stage === 'all' ? '' : `?stage=${stage}`;
  const { data, error, loading } = useApi(`/portfolio/journal/${qs}`,
                                          { poll: JOURNAL_POLL_MS });
  const entries = unwrapDRF(data);
  const loaded = !loading;

  return (
    <div className="view-enter">
      <PageHead
        title="Agent Journal"
        subtitle="Every decision the agentic layer made — analyst verdicts, exits, session cycles — and why" />

      <div className="card">
        {/* Stage filter chips */}
        <div className="row gap-8" style={{ marginBottom: 14, flexWrap: 'wrap' }}>
          {STAGE_FILTERS.map((s) => (
            <button key={s}
                    className={'chip ' + (stage === s ? 'chip-active' : '')}
                    style={{
                      padding: '4px 12px', borderRadius: 999, fontSize: 12,
                      border: '1px solid var(--line)', cursor: 'pointer',
                      background: stage === s ? 'var(--text)' : 'transparent',
                      color: stage === s ? 'var(--bg)' : 'var(--text-2)',
                    }}
                    onClick={() => setStage(s)}>
              {s}
            </button>
          ))}
        </div>

        {error && (
          <div className="muted" style={{ color: 'var(--red)', marginBottom: 12 }}>
            error: {error}
            {/fetch|network/i.test(error)
              ? `. Is the Django API running on ${window.FINPILOT_API}?`
              : ''}
          </div>
        )}

        {loaded && !error && entries.length === 0 && (
          <div className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
            No journal entries yet. The journal fills up when the agent runs:
            <br />• <code>python scripts/run_trading_session.py</code> — the
            market-hours supervisor (cycles, exits)
            <br />• the daily Celery tasks with <code>GEMINI_API_KEY</code> set
            — analyst verdicts per proposed trade
          </div>
        )}

        {entries.map((e) => (
          <div key={e.id} className="row" style={{
            padding: '10px 0', borderTop: '1px solid var(--line)',
            alignItems: 'baseline', gap: 12,
          }}>
            <span className="mono muted" style={{ fontSize: 11, minWidth: 130 }}>
              {new Date(e.created_at).toLocaleString('en-IN', {
                timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short',
                hour: '2-digit', minute: '2-digit', second: '2-digit',
              })}
            </span>
            <span className="mono muted" style={{ fontSize: 11, minWidth: 64 }}>
              {e.stage}
            </span>
            <span className="mono" style={{
              fontSize: 12, minWidth: 72, fontWeight: 600,
              color: decisionColor(e.decision),
            }}>
              {e.decision}
            </span>
            <span className="mono" style={{ fontSize: 12, minWidth: 110 }}>
              {e.symbol || '—'}
            </span>
            <span className="muted" style={{ fontSize: 12, flex: 1, lineHeight: 1.5 }}>
              {e.detail}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { JournalView });
