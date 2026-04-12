interface Category {
  id: string;
  label: string;
  count: number;
}

interface CategoryTabsProps {
  categories: Category[];
  activeId: string;
  onChange: (id: string) => void;
}

export default function CategoryTabs({ categories, activeId, onChange }: CategoryTabsProps) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        marginBottom: 16,
      }}
    >
      {categories.map(({ id, label, count }) => {
        const isActive = id === activeId;
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            style={{
              padding: '6px 12px',
              borderRadius: 20,
              fontSize: 12,
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
              background: isActive
                ? 'linear-gradient(90deg, #22c55e, #4ade80)'
                : 'rgba(255,255,255,0.06)',
              color: isActive ? '#052e16' : '#b4c0cc',
              boxShadow: isActive ? '0 0 8px rgba(74,222,128,0.4)' : 'none',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {label}
            <span
              style={{
                fontSize: 11,
                padding: '1px 6px',
                borderRadius: 10,
                backgroundColor: isActive
                  ? 'rgba(5,46,22,0.3)'
                  : 'rgba(255,255,255,0.1)',
              }}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
