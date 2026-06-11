import { useTranslation } from 'react-i18next';

interface ViewerToolbarProps {
  zoom: number;
  currentPage: number;
  numPages: number;
  isTrialMode: boolean;
  formattingOption: string;
  onZoomChange: (zoom: number) => void;
  onPageChange: (page: number) => void;
  onFormattingChange: (opt: string) => void;
  onBack: () => void;
  onDownload: () => void;
}

export default function ViewerToolbar({
  zoom,
  currentPage,
  numPages,
  isTrialMode,
  formattingOption,
  onZoomChange,
  onPageChange,
  onFormattingChange,
  onBack,
  onDownload,
}: ViewerToolbarProps) {
  const { t } = useTranslation();

  return (
    <div className="docbar">
      {/* Back */}
      <button
        onClick={onBack}
        className="tb-btn ghost"
        aria-label="Retour"
        title="Retour"
        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
      >
        <i className="ti ti-arrow-left" style={{ fontSize: '14px' }} aria-hidden="true" />
        <span>Retour</span>
      </button>

      {/* Zoom */}
      <button
        onClick={() => onZoomChange(zoom >= 2.0 ? 1.0 : +(zoom + 0.5).toFixed(1))}
        className="tb-btn ghost"
        aria-label="Zoom"
        title="Zoom"
        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
      >
        <i className="ti ti-zoom-in" style={{ fontSize: '14px' }} aria-hidden="true" />
        <span>{Math.round(zoom * 100)}%</span>
      </button>

      {/* Formatting */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          borderLeft: '1px solid var(--color-border-secondary)',
          paddingLeft: '12px',
          marginLeft: '6px',
        }}
      >
        <i
          className="ti ti-settings"
          style={{ fontSize: '14px', color: 'var(--color-text-secondary)' }}
          aria-hidden="true"
        />
        <select
          value={formattingOption}
          onChange={(e) => onFormattingChange(e.target.value)}
          aria-label="Options de mise en forme"
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--color-text-primary)',
            fontSize: '13px',
            fontWeight: 500,
            outline: 'none',
            cursor: 'pointer',
            paddingRight: '8px',
            fontFamily: 'inherit',
          }}
        >
          <option value="auto-fit">{t('viewer.fmt_auto_fit')}</option>
          <option value="preserve">{t('viewer.fmt_preserve')}</option>
          <option value="optimize-spacing">{t('viewer.fmt_optimize')}</option>
          <option value="adjust-margins">{t('viewer.fmt_adjust_margins')}</option>
        </select>
      </div>

      <div className="spacer" />

      {/* Page controls */}
      <div className="pg-ctrl">
        <button
          className="pg-arrow"
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          aria-label="Page précédente"
        >
          <i className="ti ti-chevron-left" style={{ fontSize: '12px' }} />
        </button>
        <span className="pg-num">
          {currentPage} / {numPages}
        </span>
        <button
          className="pg-arrow"
          onClick={() => onPageChange(Math.min(numPages, currentPage + 1))}
          disabled={currentPage >= numPages}
          aria-label="Page suivante"
        >
          <i className="ti ti-chevron-right" style={{ fontSize: '12px' }} />
        </button>
      </div>

      {/* Download */}
      <button
        onClick={() => {
          if (isTrialMode) {
            document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
            return;
          }
          onDownload();
        }}
        className="tb-btn ghost"
        aria-label="Télécharger la traduction"
        title="Télécharger la traduction"
        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
      >
        <i className="ti ti-download" style={{ fontSize: '14px' }} aria-hidden="true" />
      </button>
    </div>
  );
}
