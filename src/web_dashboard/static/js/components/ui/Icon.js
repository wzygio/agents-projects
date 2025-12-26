// src/web_dashboard/static/js/components/ui/Icon.js
const { useEffect, useRef } = React;

// 定义全局组件 Icon
window.Icon = ({ name, size = 20, className = "" }) => {
    const iconContainerRef = useRef(null);
    useEffect(() => {
        if (!iconContainerRef.current || !window.lucide) return;
        iconContainerRef.current.innerHTML = '';
        const tempIcon = document.createElement('i');
        tempIcon.setAttribute('data-lucide', name);
        iconContainerRef.current.appendChild(tempIcon);
        window.lucide.createIcons({
            root: iconContainerRef.current,
            nameAttr: 'data-lucide',
            attrs: { class: className, width: size, height: size }
        });
    }, [name, size, className]);
    return <span ref={iconContainerRef} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }} />;
};