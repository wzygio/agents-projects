// src/web_dashboard/static/js/components/ui/ResultCapsule.js

window.ResultCapsule = ({ result }) => {
    if (!result) return null;
    const isFile = result.type === 'file';
    const iconName = isFile ? 'file-check' : 'external-link';
    const typeClass = isFile ? 'type-file' : 'type-link';
    
    // 注意：这里使用了 window.Icon
    return (
        <a href={result.url} target="_blank" className={`artifact-capsule ${typeClass}`} onClick={(e) => e.stopPropagation()}>
            <span className="capsule-icon-wrapper"><window.Icon name={iconName} size={14} /></span>
            <span>{result.label}</span>
        </a>
    );
};