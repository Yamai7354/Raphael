"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

interface Resource {
    name: string;
    cpu: number | null;
    ram: number | null;
    vram: number | null;
}

export const ResourceMonitor = ({ resources }: { resources: Resource[] }) => {
    // Format for the chart - resources now comes as a historical array from stats.json
    const data = resources.map(r => ({
        name: r.name,
        cpu: r.cpu || 0,
        ram: r.ram || 0,
        vram: r.vram || 0
    }));

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="glass-card h-[350px] flex flex-col gap-4">
                <div className="flex justify-between items-center px-2">
                    <h3 className="font-bold text-lg premium-gradient-text uppercase tracking-widest text-[10px]">CPU & RAM Telemetry</h3>
                    <div className="flex gap-4">
                        <div className="flex items-center gap-1.5">
                            <div className="w-2 h-2 rounded-full bg-blue-500" />
                            <span className="text-[8px] text-muted-foreground uppercase font-bold">CPU</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="w-2 h-2 rounded-full bg-purple-500" />
                            <span className="text-[8px] text-muted-foreground uppercase font-bold">RAM</span>
                        </div>
                    </div>
                </div>
                <div className="flex-1 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data}>
                            <defs>
                                <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                                </linearGradient>
                                <linearGradient id="colorRam" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3}/>
                                    <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <XAxis 
                                dataKey="name" 
                                stroke="#555" 
                                fontSize={8} 
                                tickLine={false} 
                                axisLine={false} 
                            />
                            <YAxis 
                                stroke="#555" 
                                fontSize={8} 
                                tickLine={false} 
                                axisLine={false} 
                                tickFormatter={(value) => `${value}%`}
                            />
                            <Tooltip 
                                contentStyle={{ 
                                    backgroundColor: 'rgba(0,0,0,0.8)', 
                                    border: '1px solid rgba(255,255,255,0.1)',
                                    borderRadius: '12px',
                                    backdropFilter: 'blur(10px)',
                                    fontSize: '10px'
                                }}
                            />
                            <Area 
                                type="monotone" 
                                dataKey="cpu" 
                                stroke="#3b82f6" 
                                fillOpacity={1} 
                                fill="url(#colorCpu)" 
                                strokeWidth={2}
                                name="CPU %"
                            />
                            <Area 
                                type="monotone" 
                                dataKey="ram" 
                                stroke="#a855f7" 
                                fillOpacity={1} 
                                fill="url(#colorRam)" 
                                strokeWidth={2}
                                name="RAM %"
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="glass-card h-[350px] flex flex-col gap-4">
                <div className="flex justify-between items-center px-2">
                    <h3 className="font-bold text-lg premium-gradient-text uppercase tracking-widest text-[10px]">VRAM Load Factor</h3>
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-pink-500" />
                        <span className="text-[8px] text-muted-foreground uppercase font-bold">VRAM</span>
                    </div>
                </div>
                <div className="flex-1 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                            <XAxis 
                                dataKey="name" 
                                stroke="#555" 
                                fontSize={8} 
                                tickLine={false} 
                                axisLine={false} 
                            />
                            <YAxis 
                                stroke="#555" 
                                fontSize={8} 
                                tickLine={false} 
                                axisLine={false} 
                                tickFormatter={(value) => `${value}%`}
                            />
                            <Tooltip 
                                contentStyle={{ 
                                    backgroundColor: 'rgba(0,0,0,0.8)', 
                                    border: '1px solid rgba(255,255,255,0.1)',
                                    borderRadius: '12px',
                                    backdropFilter: 'blur(10px)',
                                    fontSize: '10px'
                                }}
                            />
                            <Line 
                                type="stepAfter" 
                                dataKey="vram" 
                                stroke="#ec4899" 
                                strokeWidth={3} 
                                dot={false}
                                name="VRAM %"
                                animationDuration={300}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
};
