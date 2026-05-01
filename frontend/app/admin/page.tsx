'use client';

import { useEffect, useState } from 'react';
import {
  createAdminSource,
  getAdminOverview,
  getAdminSettings,
  getAdminSources,
  runAdminIncremental,
  runAdminSourceDiscovery,
  runAdminSource,
  updateAdminSettings,
  updateAdminSource,
} from '@/lib/api';
import { AdminOverview, AdminSettings, CrawlSource } from '@/lib/types';

const API_KEY_STORAGE = 'acg:admin:api-key';

const defaultSettings: AdminSettings = {
  _id: 'admin',
  auto_incremental_enabled: false,
  incremental_interval_minutes: 60,
  incremental_limit: 20,
  incremental_min_hours: 6,
  auto_discover_enabled: false,
  auto_source_discovery_enabled: false,
  source_discovery_interval_minutes: 180,
};

export default function AdminPage() {
  const [apiKey, setApiKey] = useState('');
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [settings, setSettings] = useState<AdminSettings>(defaultSettings);
  const [sources, setSources] = useState<CrawlSource[]>([]);
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({
    name: '',
    domain: '',
    seed_url: '',
    homepage_url: '',
    category_pages: '',
    recent_pages: '',
    max_depth: 3,
    discovery_max_depth: 1,
    enabled: true,
    notes: '',
  });

  useEffect(() => {
    const stored = window.localStorage.getItem(API_KEY_STORAGE) || '';
    if (stored) {
      setApiKey(stored);
    }
  }, []);

  async function loadAll(key: string) {
    setLoading(true);
    setError('');
    try {
      const [overviewData, settingsData, sourcesData] = await Promise.all([
        getAdminOverview(key),
        getAdminSettings(key),
        getAdminSources(key),
      ]);
      setOverview(overviewData);
      setSettings(settingsData);
      setSources(sourcesData.data);
      setConnected(true);
      window.localStorage.setItem(API_KEY_STORAGE, key);
    } catch (err) {
      setConnected(false);
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveSettings() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const updated = await updateAdminSettings(apiKey, {
        auto_incremental_enabled: settings.auto_incremental_enabled,
        incremental_interval_minutes: Number(settings.incremental_interval_minutes),
        incremental_limit: Number(settings.incremental_limit),
        incremental_min_hours: Number(settings.incremental_min_hours),
        auto_discover_enabled: settings.auto_discover_enabled,
        auto_source_discovery_enabled: settings.auto_source_discovery_enabled,
        source_discovery_interval_minutes: Number(settings.source_discovery_interval_minutes),
      });
      setSettings(updated);
      setMessage('调度设置已保存');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateSource() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      await createAdminSource(apiKey, {
        name: form.name,
        domain: form.domain,
        seed_url: form.seed_url,
        homepage_url: form.homepage_url,
        category_pages: splitLines(form.category_pages),
        recent_pages: splitLines(form.recent_pages),
        max_depth: Number(form.max_depth),
        discovery_max_depth: Number(form.discovery_max_depth),
        enabled: form.enabled,
        notes: form.notes,
      });
      setForm({
        name: '',
        domain: '',
        seed_url: '',
        homepage_url: '',
        category_pages: '',
        recent_pages: '',
        max_depth: 3,
        discovery_max_depth: 1,
        enabled: true,
        notes: '',
      });
      setMessage('自定义爬虫源已添加');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败');
    } finally {
      setLoading(false);
    }
  }

  async function toggleSource(source: CrawlSource) {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      await updateAdminSource(apiKey, source._id, { enabled: !source.enabled });
      setMessage(`已${source.enabled ? '停用' : '启用'} ${source.name}`);
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSource(sourceId: string) {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      await runAdminSource(apiKey, sourceId);
      setMessage('已触发单站抓取');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '触发失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunIncremental() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const result = await runAdminIncremental(apiKey);
      setMessage(result.started ? `增量任务状态：${result.status}` : result.reason || '未启动');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '增量任务失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSourceDiscovery() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const result = await runAdminSourceDiscovery(apiKey);
      setMessage(result.started ? '站点级发现任务已转入后台执行' : result.reason || '未启动');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '站点发现任务失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-grain px-4 py-8 md:px-8 xl:px-10">
      <div className="mx-auto max-w-[1600px]">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex rounded-full border border-ember/30 bg-ember/10 px-4 py-2 text-xs uppercase tracking-[0.28em] text-parchment/80">
              Admin Console
            </div>
            <h1 className="text-4xl font-semibold text-parchment">视频机器人管理台</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-parchment/70">
              配置自动增量巡检、自定义爬虫站点，并手动触发单站抓取。
            </p>
          </div>
        </div>

        <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_160px]">
            <label className="block">
              <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">Admin API Key</div>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="输入服务端 ADMIN_API_KEY"
                className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition placeholder:text-ash focus:border-ember/60"
              />
            </label>
            <button
              type="button"
              onClick={() => loadAll(apiKey)}
              disabled={!apiKey || loading}
              className="rounded-2xl bg-ember px-4 py-3 text-sm font-semibold text-black transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {connected ? '重新连接' : '连接后台'}
            </button>
          </div>
          {message ? <p className="mt-4 text-sm text-emerald-300">{message}</p> : null}
          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
        </section>

        {connected ? (
          <div className="mt-8 grid gap-8">
            <section className="grid gap-4 md:grid-cols-3">
              <Card label="手动爬虫源">{overview?.source_count ?? 0}</Card>
              <Card label="启用中的源">{overview?.enabled_source_count ?? 0}</Card>
              <Card label="上次增量状态">{overview?.settings.last_incremental_status || 'idle'}</Card>
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              <Card label="上次站点发现状态">{overview?.settings.last_source_discovery_status || 'idle'}</Card>
              <Card label="站点发现周期">{settings.source_discovery_interval_minutes} 分钟</Card>
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-semibold text-parchment">自动调度设置</h2>
                  <p className="mt-2 text-sm text-parchment/70">动画级增量巡检与站点级发现任务分开调度，站点级发现会在后台异步执行。</p>
                </div>
                <button
                  type="button"
                  onClick={handleRunIncremental}
                  disabled={loading}
                  className="rounded-full border border-ember/40 bg-ember/15 px-4 py-2 text-sm text-parchment transition hover:bg-ember/25"
                >
                  立即执行增量巡检
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <ToggleField
                  label="启用自动增量"
                  checked={settings.auto_incremental_enabled}
                  onChange={(value) => setSettings((current) => ({ ...current, auto_incremental_enabled: value }))}
                />
                <NumberField
                  label="巡检间隔(分钟)"
                  value={settings.incremental_interval_minutes}
                  onChange={(value) => setSettings((current) => ({ ...current, incremental_interval_minutes: value }))}
                />
                <NumberField
                  label="每轮数量"
                  value={settings.incremental_limit}
                  onChange={(value) => setSettings((current) => ({ ...current, incremental_limit: value }))}
                />
                <NumberField
                  label="最小间隔(小时)"
                  value={settings.incremental_min_hours}
                  onChange={(value) => setSettings((current) => ({ ...current, incremental_min_hours: value }))}
                />
              </div>

              <div className="mt-4">
                <ToggleField
                  label="自动 discover 预留开关"
                  checked={settings.auto_discover_enabled}
                  onChange={(value) => setSettings((current) => ({ ...current, auto_discover_enabled: value }))}
                />
              </div>

              <button
                type="button"
                onClick={handleSaveSettings}
                disabled={loading}
                className="mt-5 rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110"
              >
                保存调度设置
              </button>

              {overview?.settings.last_incremental_output ? (
                <pre className="scrollbar-thin mt-5 max-h-60 overflow-auto rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-parchment/75">
                  {overview.settings.last_incremental_output}
                </pre>
              ) : null}
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-semibold text-parchment">站点级增量发现</h2>
                  <p className="mt-2 text-sm text-parchment/70">只回访手动源配置的入口页，浅抓取发现新动画，不深度全站扩散。</p>
                </div>
                <button
                  type="button"
                  onClick={handleRunSourceDiscovery}
                  disabled={loading}
                  className="rounded-full border border-ember/40 bg-ember/15 px-4 py-2 text-sm text-parchment transition hover:bg-ember/25"
                >
                  立即执行站点发现
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <ToggleField
                  label="启用站点级增量发现"
                  checked={settings.auto_source_discovery_enabled}
                  onChange={(value) => setSettings((current) => ({ ...current, auto_source_discovery_enabled: value }))}
                />
                <NumberField
                  label="发现周期(分钟)"
                  value={settings.source_discovery_interval_minutes}
                  onChange={(value) => setSettings((current) => ({ ...current, source_discovery_interval_minutes: value }))}
                />
              </div>

              {overview?.settings.last_source_discovery_output ? (
                <pre className="scrollbar-thin mt-5 max-h-60 overflow-auto rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-parchment/75">
                  {overview.settings.last_source_discovery_output}
                </pre>
              ) : null}
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <h2 className="text-2xl font-semibold text-parchment">新增自定义爬虫源</h2>
              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <TextField label="名称" value={form.name} onChange={(value) => setForm((current) => ({ ...current, name: value }))} />
                <TextField label="域名" value={form.domain} onChange={(value) => setForm((current) => ({ ...current, domain: value }))} />
                <TextField label="seed_url" value={form.seed_url} onChange={(value) => setForm((current) => ({ ...current, seed_url: value }))} />
                <TextField label="首页 URL" value={form.homepage_url} onChange={(value) => setForm((current) => ({ ...current, homepage_url: value }))} />
                <TextAreaField label="分类页列表(每行一个)" value={form.category_pages} onChange={(value) => setForm((current) => ({ ...current, category_pages: value }))} />
                <TextAreaField label="最近更新页列表(每行一个)" value={form.recent_pages} onChange={(value) => setForm((current) => ({ ...current, recent_pages: value }))} />
                <NumberField label="最大深度" value={form.max_depth} onChange={(value) => setForm((current) => ({ ...current, max_depth: value }))} />
                <NumberField label="发现任务深度" value={form.discovery_max_depth} onChange={(value) => setForm((current) => ({ ...current, discovery_max_depth: value }))} />
                <TextField label="备注" value={form.notes} onChange={(value) => setForm((current) => ({ ...current, notes: value }))} />
                <ToggleField label="创建后启用" checked={form.enabled} onChange={(value) => setForm((current) => ({ ...current, enabled: value }))} />
              </div>
              <button
                type="button"
                onClick={handleCreateSource}
                disabled={loading || !form.name || (!form.domain && !form.seed_url)}
                className="mt-5 rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                添加爬虫源
              </button>
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <h2 className="text-2xl font-semibold text-parchment">手动爬虫源列表</h2>
              <div className="mt-5 grid gap-4">
                {sources.map((source) => (
                  <div key={source._id} className="rounded-[24px] border border-white/10 bg-black/20 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="text-lg font-semibold text-parchment">{source.name}</div>
                        <div className="mt-2 text-sm text-parchment/70">
                          {source.seed_url || source.domain || '未配置入口'}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-ash">
                          <span>max_depth={source.max_depth}</span>
                          <span>discovery_depth={source.discovery_max_depth ?? 1}</span>
                          <span>{source.enabled ? 'enabled' : 'disabled'}</span>
                          <span>{source.last_run_status || 'never-run'}</span>
                          <span>{source.last_discovery_status || 'never-discovery'}</span>
                        </div>
                        {source.homepage_url ? <div className="mt-2 text-xs text-parchment/55">首页: {source.homepage_url}</div> : null}
                        {!!source.category_pages?.length ? <div className="mt-1 text-xs text-parchment/55">分类页: {source.category_pages.length} 个</div> : null}
                        {!!source.recent_pages?.length ? <div className="mt-1 text-xs text-parchment/55">最近更新页: {source.recent_pages.length} 个</div> : null}
                        {source.notes ? <div className="mt-2 text-sm text-parchment/60">{source.notes}</div> : null}
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => toggleSource(source)}
                          className="rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment"
                        >
                          {source.enabled ? '停用' : '启用'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRunSource(source._id)}
                          className="rounded-full bg-ember px-4 py-2 text-sm font-semibold text-black transition hover:brightness-110"
                        >
                          立即抓取
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                {!sources.length ? <div className="text-sm text-ash">暂无自定义爬虫源。</div> : null}
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </main>
  );
}

function Card({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card">
      <div className="text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <div className="mt-4 text-4xl font-semibold text-parchment">{children}</div>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition focus:border-ember/60"
      />
    </label>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="block">
      <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <input
        type="number"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition focus:border-ember/60"
      />
    </label>
  );
}

function TextAreaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition focus:border-ember/60"
      />
    </label>
  );
}

function ToggleField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
      <span className="text-sm text-parchment/80">{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 accent-[#c96b2c]" />
    </label>
  );
}

function splitLines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}
