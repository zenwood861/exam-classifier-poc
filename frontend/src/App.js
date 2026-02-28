import React, { useState, useRef, useCallback } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

/* ─── Design Tokens ─────────────────────────────────────────────────────── */
const T = {
  primary: '#1E40AF',
  primaryLight: '#3B82F6',
  primaryFaint: '#DBEAFE',
  accent: '#F59E0B',
  bg: '#F8FAFC',
  surface: '#FFFFFF',
  text: '#0F172A',
  textSec: '#334155',
  textMuted: '#64748B',
  textFaint: '#94A3B8',
  border: '#E2E8F0',
  borderLight: '#F1F5F9',
  green: '#16A34A',
  greenBg: '#F0FDF4',
  greenBorder: '#BBF7D0',
  orange: '#D97706',
  orangeBg: '#FFFBEB',
  orangeBorder: '#FDE68A',
  red: '#DC2626',
  redBg: '#FEF2F2',
  redBorder: '#FECACA',
  radius: '8px',
  radiusLg: '12px',
  font: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  fontMono: "'Fira Code', 'SF Mono', monospace",
  shadow: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
  shadowHover: '0 4px 12px rgba(0,0,0,0.08)',
  transition: 'all 0.15s ease',
};

/* ─── SVG Icons ─────────────────────────────────────────────────────────── */
const Icon = {
  upload: (s = 18) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  ),
  file: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
    </svg>
  ),
  check: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  ),
  alert: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  tag: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>
    </svg>
  ),
  grid: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
    </svg>
  ),
  list: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
    </svg>
  ),
  expand: (s = 12) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
    </svg>
  ),
  zap: (s = 20) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    </svg>
  ),
  layers: (s = 20) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
    </svg>
  ),
  search: (s = 20) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  ),
};

/* ─── Confidence → color ────────────────────────────────────────────────── */
function confStyle(conf) {
  if (conf >= 0.80) return { bg: T.greenBg, color: T.green, border: T.greenBorder };
  if (conf >= 0.70) return { bg: T.orangeBg, color: T.orange, border: T.orangeBorder };
  return { bg: T.redBg, color: T.red, border: T.redBorder };
}

/* ─── Slot Tag ──────────────────────────────────────────────────────────── */
function SlotTag({ slot }) {
  const { bg, color, border } = confStyle(slot.confidence ?? 0);
  const pct = Math.round((slot.confidence ?? 0) * 100);
  const parts = [];
  if (slot.C) parts.push(slot.D ? `${slot.C} ${slot.D}` : slot.C);
  if (slot.F || slot.E) parts.push(slot.F || slot.E);
  if (slot.H || slot.G) parts.push(slot.H || slot.G);
  if (slot.J || slot.I) parts.push(slot.J || slot.I);
  const label = parts.filter(Boolean).join(' / ') || '\u2014';

  const tooltip = [
    `A: ${slot.A || ''} \u2014 ${slot.B || ''}`,
    `C: ${slot.C || ''} \u2014 ${slot.D || ''}`,
    `E: ${slot.E || ''} \u2014 ${slot.F || ''}`,
    `G: ${slot.G || ''} \u2014 ${slot.H || ''}`,
    `I: ${slot.I || ''} \u2014 ${slot.J || ''}`,
    `Confidence: ${pct}%`,
  ].join('\n');

  return (
    <span title={tooltip} style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 10px', margin: '2px 4px 2px 0',
      borderRadius: '6px', fontSize: '11px', fontWeight: 500,
      fontFamily: T.fontMono, letterSpacing: '-0.01em',
      background: bg, color, border: `1px solid ${border}`,
      cursor: 'default', transition: T.transition, lineHeight: '1.4',
    }}>
      {label}
      <span style={{ opacity: 0.6, fontSize: '10px', fontWeight: 400 }}>{pct}%</span>
    </span>
  );
}

/* ─── Question Card ─────────────────────────────────────────────────────── */
function QuestionCard({ q }) {
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const needsReview = q.slots.length === 0 || q.slots.every(s => (s.confidence ?? 0) < 0.70);
  const imgUrl = `${API_BASE}${q.image_url}`;
  const fullUrl = q.full_page_url ? `${API_BASE}${q.full_page_url}` : imgUrl;
  const visible = showAll ? q.slots : q.slots.slice(0, 3);
  const extra = q.slots.length - 3;

  return (
    <div style={{
      background: T.surface, borderRadius: T.radiusLg,
      border: `1px solid ${needsReview ? T.orangeBorder : T.border}`,
      padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px',
      transition: T.transition, boxShadow: T.shadow,
    }}
      onMouseEnter={e => e.currentTarget.style.boxShadow = T.shadowHover}
      onMouseLeave={e => e.currentTarget.style.boxShadow = T.shadow}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
          <span style={{
            background: T.primary, color: '#fff', borderRadius: '6px', padding: '2px 10px',
            fontWeight: 600, fontSize: '12px', fontFamily: T.fontMono,
            whiteSpace: 'nowrap', letterSpacing: '-0.02em',
          }}>
            {q.label || `Q${q.no}`}
          </span>
          {q.lang && (
            <span style={{
              fontSize: '10px', fontWeight: 600, color: q.lang === 'CH' ? '#B91C1C' : T.primary,
              background: q.lang === 'CH' ? '#FEF2F2' : T.primaryFaint,
              borderRadius: '4px', padding: '2px 6px', whiteSpace: 'nowrap',
              fontFamily: T.fontMono,
            }}>
              {q.lang === 'CH' ? 'CN' : 'EN'}
            </span>
          )}
          {q.pdf && (
            <span style={{
              fontSize: '11px', color: T.textFaint, background: T.borderLight,
              borderRadius: '4px', padding: '2px 6px', whiteSpace: 'nowrap',
              overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100px',
            }}>
              {q.pdf}
            </span>
          )}
        </div>
        <span style={{ fontSize: '11px', color: T.textFaint, fontFamily: T.fontMono }}>p.{q.page}</span>
      </div>

      {q.exercise && (
        <div style={{
          fontSize: '11px', color: T.textMuted, fontStyle: 'italic',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>{q.exercise}</div>
      )}

      <div onClick={() => setExpanded(v => !v)} style={{
        fontSize: '13px', lineHeight: 1.6, color: T.text, cursor: 'pointer',
        display: '-webkit-box', WebkitLineClamp: expanded ? 'unset' : 3,
        WebkitBoxOrient: 'vertical', overflow: expanded ? 'visible' : 'hidden',
      }}>
        {q.text}
      </div>

      <a href={fullUrl} target="_blank" rel="noreferrer" style={{
        display: 'block', borderRadius: T.radius, overflow: 'hidden',
        border: `1px solid ${T.border}`, background: T.bg,
        position: 'relative', cursor: 'pointer',
      }}>
        <img src={imgUrl} alt={`Q${q.no}`} style={{
          width: '100%', maxHeight: '100px', objectFit: 'contain',
          objectPosition: 'left top', display: 'block',
        }} onError={e => { e.target.parentElement.style.display = 'none'; }} />
        <span style={{
          position: 'absolute', top: '6px', right: '6px',
          background: 'rgba(0,0,0,0.5)', color: '#fff',
          borderRadius: '4px', padding: '2px 4px', display: 'flex', alignItems: 'center',
        }}>{Icon.expand()}</span>
      </a>

      <div style={{ minHeight: '24px' }}>
        {q.slots.length === 0 ? (
          <span style={{ fontSize: '12px', color: T.textFaint }}>No classification match</span>
        ) : (<>
          {visible.map((s, i) => <SlotTag key={i} slot={s} />)}
          {!showAll && extra > 0 && (
            <span onClick={() => setShowAll(true)} style={{
              display: 'inline-block', padding: '3px 10px', margin: '2px 4px',
              borderRadius: '6px', fontSize: '11px', fontWeight: 500,
              background: T.borderLight, color: T.textMuted,
              cursor: 'pointer', border: `1px solid ${T.border}`, transition: T.transition,
            }}>+{extra} more</span>
          )}
        </>)}
      </div>

      {needsReview && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: T.orange, fontWeight: 500 }}>
          {Icon.alert()}<span>Needs manual review</span>
        </div>
      )}
    </div>
  );
}

/* ─── Passage Group Card (reading comprehension) ───────────────────────── */
function PassageGroupCard({ group }) {
  const [showAll, setShowAll] = useState(false);
  const [expandedPassage, setExpandedPassage] = useState(false);
  const visible = showAll ? group.slots : group.slots.slice(0, 3);
  const extra = group.slots.length - 3;

  return (
    <div style={{
      background: T.surface, borderRadius: T.radiusLg,
      border: `1px solid ${T.primary}33`,
      boxShadow: T.shadow, overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px', background: T.primaryFaint,
        borderBottom: `1px solid ${T.primary}22`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: '28px', height: '28px', borderRadius: '8px',
            background: T.primary, color: '#fff',
          }}>
            {Icon.file(14)}
          </span>
          <div>
            <div style={{ fontSize: '14px', fontWeight: 700, color: T.text }}>
              {group.exercise}
            </div>
            <div style={{ fontSize: '11px', color: T.textMuted }}>
              {group.questions.length} questions
              {group.lang && <span> &middot; {group.lang === 'CH' ? 'CN' : group.lang}</span>}
              {group.pdf && <span> &middot; {group.pdf}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Page images (the passage / article) */}
      <div style={{ padding: '16px 20px', borderBottom: `1px solid ${T.border}` }}>
        <div style={{ fontSize: '11px', fontWeight: 600, color: T.textMuted, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Passage
        </div>
        <div style={{
          display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px',
        }}>
          {group.page_urls.map((url, i) => (
            <a key={i} href={`${API_BASE}${url}`} target="_blank" rel="noreferrer" style={{
              flexShrink: 0, borderRadius: T.radius, overflow: 'hidden',
              border: `1px solid ${T.border}`, position: 'relative',
            }}>
              <img src={`${API_BASE}${url}`} alt={`Page ${i + 1}`} style={{
                height: '200px', width: 'auto', display: 'block',
              }} onError={e => { e.target.parentElement.style.display = 'none'; }} />
              <span style={{
                position: 'absolute', top: '4px', right: '4px',
                background: 'rgba(0,0,0,0.5)', color: '#fff',
                borderRadius: '4px', padding: '2px 6px', fontSize: '10px', fontWeight: 600,
              }}>p.{i + 1}</span>
              <span style={{
                position: 'absolute', bottom: '4px', right: '4px',
                background: 'rgba(0,0,0,0.5)', color: '#fff',
                borderRadius: '4px', padding: '2px 4px', display: 'flex', alignItems: 'center',
              }}>{Icon.expand()}</span>
            </a>
          ))}
        </div>
        {group.passage_text && (
          <div
            onClick={() => setExpandedPassage(v => !v)}
            style={{
              marginTop: '10px', fontSize: '12px', lineHeight: 1.6, color: T.textSec,
              cursor: 'pointer', background: T.bg, padding: '10px 12px',
              borderRadius: T.radius, border: `1px solid ${T.border}`,
              display: '-webkit-box', WebkitLineClamp: expandedPassage ? 'unset' : 3,
              WebkitBoxOrient: 'vertical', overflow: expandedPassage ? 'visible' : 'hidden',
            }}
          >
            {group.passage_text}
          </div>
        )}
      </div>

      {/* Group-level classification */}
      {group.slots.length > 0 && (
        <div style={{ padding: '10px 20px', borderBottom: `1px solid ${T.border}`, background: T.bg }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: T.textMuted, marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Group Classification
          </div>
          {visible.map((s, i) => <SlotTag key={i} slot={s} />)}
          {!showAll && extra > 0 && (
            <span onClick={() => setShowAll(true)} style={{
              display: 'inline-block', padding: '3px 10px', margin: '2px 4px',
              borderRadius: '6px', fontSize: '11px', fontWeight: 500,
              background: T.borderLight, color: T.textMuted,
              cursor: 'pointer', border: `1px solid ${T.border}`,
            }}>+{extra} more</span>
          )}
        </div>
      )}

      {/* Questions list */}
      <div style={{ padding: '12px 20px' }}>
        <div style={{ fontSize: '11px', fontWeight: 600, color: T.textMuted, marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Questions
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {group.questions.map((q, i) => (
            <PassageQuestion key={q.id} q={q} />
          ))}
        </div>
      </div>
    </div>
  );
}

function PassageQuestion({ q }) {
  const [showSlots, setShowSlots] = useState(false);
  return (
    <div style={{
      padding: '10px 14px', borderRadius: T.radius,
      border: `1px solid ${T.border}`, background: T.bg,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
        <span style={{
          background: T.primary, color: '#fff', borderRadius: '4px', padding: '1px 8px',
          fontWeight: 600, fontSize: '11px', fontFamily: T.fontMono, whiteSpace: 'nowrap',
          marginTop: '2px',
        }}>
          {q.label || `Q${q.no}`}
        </span>
        <div style={{ fontSize: '13px', lineHeight: 1.5, color: T.text, flex: 1 }}>
          {q.text || <span style={{ color: T.textFaint, fontStyle: 'italic' }}>(no text)</span>}
        </div>
      </div>
      {q.slots && q.slots.length > 0 && (
        <div style={{ marginTop: '6px', marginLeft: '40px' }}>
          <span onClick={() => setShowSlots(v => !v)} style={{
            fontSize: '10px', color: T.textMuted, cursor: 'pointer',
            textDecoration: 'underline',
          }}>
            {showSlots ? 'hide slots' : `${q.slots.length} slot${q.slots.length > 1 ? 's' : ''}`}
          </span>
          {showSlots && (
            <div style={{ marginTop: '4px' }}>
              {q.slots.slice(0, 5).map((s, i) => <SlotTag key={i} slot={s} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Stats Bar ─────────────────────────────────────────────────────────── */
function StatsBar({ questions, groups = [] }) {
  const groupQs = groups.flatMap(g => g.questions || []);
  const allQs = [...questions, ...groupQs];
  const total = allQs.length;
  const withSlots = allQs.filter(q => q.slots && q.slots.length > 0).length;
  const allConf = allQs.flatMap(q => (q.slots || []).map(s => s.confidence ?? 0));
  const avg = allConf.length ? Math.round(allConf.reduce((a, b) => a + b, 0) / allConf.length * 100) : 0;
  const reviewCount = allQs.filter(q => !q.slots || q.slots.length === 0 || q.slots.every(s => (s.confidence ?? 0) < 0.70)).length;
  const exercises = new Set([
    ...questions.map(q => q.exercise),
    ...groups.map(g => g.exercise),
  ].filter(Boolean)).size;
  const pdfs = new Set([
    ...questions.map(q => q.pdf),
    ...groups.map(g => g.pdf),
  ].filter(Boolean)).size;
  const langs = [...new Set([
    ...questions.map(q => q.lang),
    ...groups.map(g => g.lang),
  ].filter(Boolean))];
  const stats = [
    ...(pdfs > 1 ? [{ label: 'Files', value: pdfs, icon: Icon.file }] : []),
    ...(langs.length > 1 ? [{ label: 'Languages', value: langs.map(l => l === 'CH' ? 'CN' : l).join(', '), icon: Icon.tag }] : []),
    { label: 'Questions', value: total, icon: Icon.grid },
    ...(groups.length > 0 ? [{ label: 'Passages', value: groups.length, icon: Icon.file }] : []),
    ...(exercises > 0 ? [{ label: 'Exercises', value: exercises, icon: Icon.list }] : []),
    { label: 'Matched', value: withSlots, icon: Icon.tag },
    { label: 'Avg confidence', value: `${avg}%`, icon: Icon.check },
    ...(reviewCount > 0 ? [{ label: 'Need review', value: reviewCount, icon: Icon.alert }] : []),
  ];
  return (
    <div style={{
      display: 'flex', gap: '16px', flexWrap: 'wrap', margin: '20px 0', padding: '16px 20px',
      background: T.surface, borderRadius: T.radiusLg, border: `1px solid ${T.border}`, boxShadow: T.shadow,
    }}>
      {stats.map((s, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: T.textFaint, display: 'flex' }}>{s.icon()}</span>
          <span style={{ fontSize: '20px', fontWeight: 700, color: T.text, fontFamily: T.fontMono }}>{s.value}</span>
          <span style={{ fontSize: '12px', color: T.textMuted }}>{s.label}</span>
          {i < stats.length - 1 && <span style={{ color: T.border, margin: '0 4px' }}>|</span>}
        </div>
      ))}
    </div>
  );
}

/* ─── Upload Hero (empty state) ─────────────────────────────────────────── */
function UploadHero({ onUpload, loading, fileRef }) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragOut = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (files.length) {
      const dt = new DataTransfer();
      files.forEach(f => dt.items.add(f));
      fileRef.current.files = dt.files;
      fileRef.current.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }, [fileRef]);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: 'calc(100vh - 72px)', padding: '40px 24px',
    }}>
      {/* Title area */}
      <div style={{ textAlign: 'center', marginBottom: '48px', maxWidth: '560px' }}>
        <h2 style={{
          fontSize: '32px', fontWeight: 800, color: T.text,
          letterSpacing: '-0.03em', lineHeight: 1.2, margin: '0 0 12px',
        }}>
          Classify exam questions<br />in seconds
        </h2>
        <p style={{ fontSize: '15px', color: T.textMuted, lineHeight: 1.6, margin: 0 }}>
          Upload a PDF exam paper. The system extracts every question using OCR,
          then classifies each one against your taxonomy instantly.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileRef.current.click()}
        style={{
          width: '100%', maxWidth: '520px', padding: '48px 40px',
          background: dragOver ? T.primaryFaint : T.surface,
          border: `2px dashed ${dragOver ? T.primaryLight : T.border}`,
          borderRadius: '16px', textAlign: 'center',
          cursor: 'pointer', transition: T.transition,
          boxShadow: dragOver ? `0 0 0 4px ${T.primaryFaint}` : T.shadow,
        }}
      >
        <div style={{
          width: '56px', height: '56px', borderRadius: '14px',
          background: T.primaryFaint, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 20px', color: T.primary,
        }}>
          {Icon.upload(28)}
        </div>
        <p style={{ fontSize: '15px', fontWeight: 600, color: T.text, margin: '0 0 6px' }}>
          {dragOver ? 'Drop PDF files here' : 'Drag and drop PDF files here'}
        </p>
        <p style={{ fontSize: '13px', color: T.textMuted, margin: '0 0 20px' }}>
          or click to browse. Multiple files supported.
        </p>
        <span style={{
          display: 'inline-block', padding: '10px 28px',
          background: T.primary, color: '#fff', borderRadius: T.radius,
          fontWeight: 600, fontSize: '14px', fontFamily: T.font,
          letterSpacing: '-0.01em', transition: T.transition,
        }}>
          Select files
        </span>
      </div>

      {/* Feature pills */}
      <div style={{
        display: 'flex', gap: '24px', marginTop: '48px', flexWrap: 'wrap',
        justifyContent: 'center',
      }}>
        {[
          { icon: Icon.search, title: 'OCR Extraction', desc: 'Reads scanned PDFs' },
          { icon: Icon.zap, title: 'Instant Classification', desc: 'Keyword matching' },
          { icon: Icon.layers, title: 'Multi-slot Tagging', desc: 'Multiple taxonomy matches' },
        ].map((f, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: '12px',
            padding: '16px 20px', background: T.surface,
            borderRadius: T.radiusLg, border: `1px solid ${T.border}`,
            minWidth: '200px', maxWidth: '240px',
          }}>
            <div style={{
              color: T.primary, flexShrink: 0, marginTop: '2px',
            }}>
              {f.icon()}
            </div>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: T.text }}>{f.title}</div>
              <div style={{ fontSize: '12px', color: T.textMuted, marginTop: '2px' }}>{f.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Spinner ───────────────────────────────────────────────────────────── */
function Spinner({ count }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: 'calc(100vh - 72px)', padding: '40px',
    }}>
      <div style={{
        display: 'inline-block', width: 44, height: 44,
        border: `3px solid ${T.border}`, borderTop: `3px solid ${T.primary}`,
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <p style={{ marginTop: 20, color: T.text, fontSize: '15px', fontWeight: 600 }}>
        Processing {count} file{count > 1 ? 's' : ''}
      </p>
      <p style={{ color: T.textMuted, fontSize: '13px', marginTop: '4px' }}>
        Extracting questions and classifying...
      </p>
    </div>
  );
}

/* ─── Main App ──────────────────────────────────────────────────────────── */
export default function App() {
  const [questions, setQuestions] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fileNames, setFileNames] = useState([]);
  const fileRef = useRef();

  const hasResults = !loading && (questions.length > 0 || groups.length > 0);

  async function handleUpload(e) {
    const fileList = Array.from(e.target.files);
    if (!fileList.length) return;
    setFileNames(fileList.map(f => f.name));
    setError('');
    setQuestions([]);
    setGroups([]);
    setLoading(true);
    const form = new FormData();
    fileList.forEach(f => form.append('files', f));
    try {
      const { data } = await axios.post(`${API_BASE}/upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600_000,
      });
      setQuestions(data.questions ?? []);
      setGroups(data.groups ?? []);
    } catch (err) {
      const msg = err.response?.data?.detail ?? err.message ?? 'Upload failed';
      setError(msg);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  return (
    <div style={{ fontFamily: T.font, background: T.bg, minHeight: '100vh' }}>
      {/* Top bar */}
      <header style={{
        background: T.surface, borderBottom: `1px solid ${T.border}`,
        padding: '0 32px', height: '56px', display: 'flex',
        alignItems: 'center', justifyContent: 'space-between',
        position: 'sticky', top: 0, zIndex: 50,
      }}>
        <h1 style={{
          fontSize: '16px', fontWeight: 700, color: T.text, margin: 0,
          letterSpacing: '-0.02em',
        }}>
          Exam Classifier
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {hasResults && (
            <button
              onClick={() => fileRef.current.click()}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '7px 16px', background: T.primary, color: '#fff',
                border: 'none', borderRadius: T.radius, fontWeight: 600,
                fontSize: '13px', fontFamily: T.font, cursor: 'pointer',
                transition: T.transition,
              }}
              onMouseEnter={e => e.currentTarget.style.background = T.primaryLight}
              onMouseLeave={e => e.currentTarget.style.background = T.primary}
            >
              {Icon.upload(14)}
              <span>Upload more</span>
            </button>
          )}
          {hasResults && fileNames.length > 0 && (
            <span style={{ fontSize: '12px', color: T.textFaint }}>
              {fileNames.length === 1 ? fileNames[0] : `${fileNames.length} files`}
            </span>
          )}
        </div>
      </header>

      {/* Hidden file input */}
      <input ref={fileRef} type="file" accept=".pdf" multiple
        style={{ display: 'none' }} onChange={handleUpload} />

      {/* Error */}
      {error && (
        <div style={{
          maxWidth: '600px', margin: '20px auto', padding: '12px 16px',
          display: 'flex', alignItems: 'center', gap: '8px',
          background: T.redBg, color: T.red, borderRadius: T.radius,
          fontSize: '13px', fontWeight: 500, border: `1px solid ${T.redBorder}`,
        }}>
          {Icon.alert()}{error}
        </div>
      )}

      {/* Upload hero (shown when no results and not loading) */}
      {!loading && questions.length === 0 && groups.length === 0 && !error && (
        <UploadHero onUpload={handleUpload} loading={loading} fileRef={fileRef} />
      )}

      {/* Loading */}
      {loading && <Spinner count={fileNames.length} />}

      {/* Results */}
      {hasResults && (
        <main style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 32px 48px' }}>
          <StatsBar questions={questions} groups={groups} />

          {/* Passage groups first */}
          {groups.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: T.textMuted, marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Reading Comprehension ({groups.reduce((n, g) => n + g.questions.length, 0)} questions in {groups.length} passage{groups.length > 1 ? 's' : ''})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {groups.map(g => <PassageGroupCard key={g.group_id} group={g} />)}
              </div>
            </div>
          )}

          {/* Standalone questions */}
          {questions.length > 0 && (
            <>
              {groups.length > 0 && (
                <div style={{ fontSize: '12px', fontWeight: 600, color: T.textMuted, marginBottom: '10px', marginTop: '24px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Standalone Questions ({questions.length})
                </div>
              )}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
                gap: '14px',
              }}>
                {questions.map(q => <QuestionCard key={q.id} q={q} />)}
              </div>
            </>
          )}
        </main>
      )}
    </div>
  );
}
