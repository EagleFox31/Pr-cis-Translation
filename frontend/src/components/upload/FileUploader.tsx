import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';

interface FileUploaderProps {
  selectedFile: File | null;
  onFileSelect: (file: File | null) => void;
}

const SUPPORTED_FORMATS = ['PDF', 'DOCX', 'TXT'];

export default function FileUploader({ selectedFile, onFileSelect }: FileUploaderProps) {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileSelect = (file: File) => {
    if (file.size > 100 * 1024 * 1024) {
      alert(t('story.error_too_large'));
      return;
    }
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['txt', 'pdf', 'docx'].includes(ext || '')) {
      alert(t('story.error_unsupported'));
      return;
    }
    onFileSelect(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  };

  const getFileIcon = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf': return '📄';
      case 'docx': return '📝';
      case 'txt': return '📃';
      default: return '📁';
    }
  };

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.pdf,.docx"
        hidden
        onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
      />

      {selectedFile ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
            padding: '14px 18px',
            borderRadius: '12px',
            border: '1.5px solid #dbeafe',
            background: '#eff6ff',
          }}
        >
          <span style={{ fontSize: '28px' }}>{getFileIcon(selectedFile.name)}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--navy)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {selectedFile.name}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--gray-500)', marginTop: '2px' }}>
              {formatFileSize(selectedFile.size)}
            </div>
          </div>
          <button
            onClick={() => onFileSelect(null)}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '16px',
              padding: '4px',
              borderRadius: '6px',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9'; e.currentTarget.style.color = '#475569'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#94a3b8'; }}
            aria-label={t('story.remove_file')}
          >
            ✕
          </button>
        </motion.div>
      ) : (
        <motion.div
          whileHover={{ scale: 1.005 }}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: `2px dashed ${isDragging ? 'var(--blue)' : 'var(--color-border-primary)'}`,
            background: isDragging ? 'var(--blue-light)' : 'var(--color-background-secondary)',
            borderRadius: '12px',
            padding: '36px 20px',
            textAlign: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {isDragging && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={{
                position: 'absolute',
                inset: 0,
                background: 'rgba(37,99,235,0.04)',
                pointerEvents: 'none',
              }}
            />
          )}

          <motion.div
            animate={isDragging ? { y: -5 } : { y: 0 }}
            style={{ color: isDragging ? 'var(--blue)' : 'var(--gray-500)', marginBottom: '10px' }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="1.5"
              stroke="currentColor"
              style={{ width: '38px', height: '38px', margin: '0 auto' }}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"
              />
            </svg>
          </motion.div>

          <p style={{ fontSize: '14px', color: isDragging ? 'var(--blue)' : 'var(--navy)', fontWeight: 600 }}>
            {isDragging ? t('story.drop_ready') : t('story.drop_text')}
          </p>
          <p style={{ fontSize: '13px', color: 'var(--gray-500)', marginTop: '5px' }}
            dangerouslySetInnerHTML={{ __html: t('story.browse_text') }}
          />
          <div style={{ display: 'flex', gap: '6px', justifyContent: 'center', marginTop: '12px' }}>
            {SUPPORTED_FORMATS.map((fmt) => (
              <span
                key={fmt}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                  fontWeight: 500,
                  padding: '3px 8px',
                  borderRadius: '4px',
                  background: 'var(--gray-100)',
                  color: 'var(--gray-500)',
                  border: '1px solid var(--gray-200)',
                }}
              >
                {fmt}
              </span>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
