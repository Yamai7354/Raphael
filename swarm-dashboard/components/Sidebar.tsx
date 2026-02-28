"use client";

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
    LayoutDashboard, Users, Brain, MessageSquare, 
    Settings, Activity, ChevronDown, ChevronRight,
    Search, Database, Zap, Shield, Globe
} from 'lucide-react';

const Sidebar = () => {
    const pathname = usePathname();
    const [swarmOpen, setSwarmOpen] = useState(true);
    const [modulesOpen, setModulesOpen] = useState(false);

    const mainNav = [
        { name: 'Overview', href: '/', icon: LayoutDashboard },
        { name: 'Real-time Stats', href: '/stats', icon: Activity },
    ];

    const swarmItems = [
        { name: 'Agent Registry', href: '/agents', icon: Users },
        { name: 'Neural Brain', href: '/brain', icon: Brain },
        { name: 'Direct Interact', href: '/interact', icon: MessageSquare },
    ];

    const moduleItems = [
        { name: 'Models', href: '/models', icon: Zap },
        { name: 'Knowledge Graph', href: '/kg', icon: Database },
        { name: 'Security Audit', href: '/security', icon: Shield },
        { name: 'Network Scanner', href: '/scanner', icon: Search },
        { name: 'Network Observatory', href: '/observatory', icon: Globe },
    ];

    const NavLink = ({ item, indent = false }: { item: any, indent?: boolean }) => {
        const active = pathname === item.href;
        return (
            <Link
                href={item.href}
                className={`flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all group ${
                    active 
                    ? 'bg-primary/20 text-primary border border-primary/20' 
                    : 'hover:bg-white/5 hover:text-primary text-muted-foreground'
                } ${indent ? 'ml-4' : ''}`}
            >
                <item.icon className={`w-4 h-4 ${active ? 'text-primary' : 'group-hover:scale-110 transition-transform'}`} />
                <span className={`text-sm font-medium ${active ? 'opacity-100' : 'opacity-80 group-hover:opacity-100'}`}>
                    {item.name}
                </span>
            </Link>
        );
    };

    return (
        <aside className="w-64 h-screen glass border-r border-white/10 flex flex-col fixed left-0 top-0 z-50">
            <div className="p-8 pb-4">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center border border-primary/40">
                        <Brain className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-xl font-black premium-gradient-text tracking-tighter">RAPHAEL</h1>
                        <p className="text-[8px] text-muted-foreground uppercase tracking-[0.2em] -mt-1 font-bold">Autonomous Swarm</p>
                    </div>
                </div>
            </div>

            <nav className="flex-1 px-4 py-4 space-y-6 overflow-y-auto custom-scrollbar">
                {/* Main Section */}
                <div className="space-y-1">
                    {mainNav.map(item => <NavLink key={item.href} item={item} />)}
                </div>

                {/* Swarm Section */}
                <div className="space-y-1">
                    <button 
                        type="button"
                        onClick={() => setSwarmOpen(!swarmOpen)}
                        className="w-full flex items-center justify-between px-4 py-2 text-[10px] font-black text-muted-foreground uppercase tracking-widest hover:text-white transition-colors"
                    >
                        <span>Core Swarm</span>
                        {swarmOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </button>
                    {swarmOpen && (
                        <div className="space-y-1 mt-1 transition-all">
                            {swarmItems.map(item => <NavLink key={item.href} item={item} />)}
                        </div>
                    )}
                </div>

                {/* Modules Section */}
                <div className="space-y-1">
                    <button 
                        type="button"
                        onClick={() => setModulesOpen(!modulesOpen)}
                        className="w-full flex items-center justify-between px-4 py-2 text-[10px] font-black text-muted-foreground uppercase tracking-widest hover:text-white transition-colors"
                    >
                        <span>Systems</span>
                        {modulesOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </button>
                    {modulesOpen && (
                        <div className="space-y-1 mt-1">
                            {moduleItems.map(item => <NavLink key={item.href} item={item} />)}
                        </div>
                    )}
                </div>
            </nav>

            <div className="p-4 border-t border-white/10 space-y-4">
                <div className="px-4 py-3 rounded-xl bg-primary/5 border border-primary/10">
                    <p className="text-[8px] text-primary uppercase font-bold tracking-widest mb-1">Status</p>
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
                        <span className="text-xs font-mono font-bold">SYSTEM_STABLE</span>
                    </div>
                </div>
                <Link 
                    href="/settings" 
                    className={`flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all ${
                        pathname === '/settings' ? 'bg-primary/20 text-primary' : 'hover:bg-white/5 text-muted-foreground'
                    }`}
                >
                    <Settings className="w-4 h-4" />
                    <span className="text-sm font-medium">Settings</span>
                </Link>
            </div>
        </aside>
    );
};

export default Sidebar;
