// src/web_dashboard/static/js/config/constants.js

// 将常量挂载到 window 对象上，模拟导出
window.PIPELINE_STEPS = [
    { id: 1, name: "异常监控扫描", icon: "activity", desc: "AI 判定异常真实性" },
    { id: 2, name: "报表自动下载", icon: "download-cloud", desc: "RPA 自动获取数据" },
    { id: 3, name: "Excel 日报生成", icon: "file-spreadsheet", desc: "生成汇总表与明细" },
    { id: 4, name: "PPT 报告生成", icon: "presentation", desc: "图表渲染与排版" }
];