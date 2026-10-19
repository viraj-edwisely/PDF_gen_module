"""Usage page: who used the app, what they made and what it cost. Read from the events table, which keeps its rows
when runs or books are deleted. Admins see the whole team; others see their own usage."""
import pandas as pd
import streamlit as st
import db
from config import TIMEZONE
from ui import is_admin, user

COLUMNS = {'sign in': 'Sign-ins', 'run started': 'Runs', 'pdf ready': 'PDFs made', 'pdf failed': 'PDFs failed', 'downloaded': 'Downloads', 'model call': 'Model calls'}

st.title('Usage')
everyone = is_admin()
c1, c2 = st.columns([1, 3])
days = c1.selectbox('Period', [1, 7, 30, 90, 365], index=2, format_func=lambda d: 'Last 24 hours' if d == 1 else f'Last {d} days')
ev = pd.DataFrame(db.sql('select at as time, email, action, run_id, cost_usd::float as cost, detail from events where at > now() - make_interval(days => %s) '
                         'and (%s or email = %s) order by at desc', (days, everyone, user())),
                  columns=['time', 'email', 'action', 'run_id', 'cost', 'detail'])
if everyone:
    people = c2.multiselect('People', sorted(ev.email.dropna().unique()), placeholder='Everyone')
    if people: ev = ev[ev.email.isin(people)]
else: c2.caption(f'Your own usage ({user()}).')
if ev.empty: st.info('Nothing was recorded in this period.'); st.stop()
ev['time'] = pd.to_datetime(ev['time'], utc=True).dt.tz_convert(TIMEZONE)

m = st.columns(4)
m[0].metric('Cost', f'${ev.cost.sum():.2f}')
m[1].metric('PDFs made', int((ev.action == 'pdf ready').sum()))
m[2].metric('Runs started', int((ev.action == 'run started').sum()))
m[3].metric('People active', ev.email.nunique())

st.subheader('By person')
per = pd.crosstab(ev.email, ev.action).reindex(columns=list(COLUMNS), fill_value=0).rename(columns=COLUMNS).rename_axis(index='Person', columns=None)
per.insert(0, 'Last active', ev.groupby('email').time.max().dt.strftime('%d %b %Y, %H:%M'))
per['Cost'] = ev.groupby('email').cost.sum()
st.dataframe(per.sort_values('Cost', ascending=False), column_config={'Cost': st.column_config.NumberColumn(format='$%.2f')})

c1, c2 = st.columns([3, 1])
c1.subheader('Cost per day')
c1.bar_chart(ev.assign(day=ev.time.dt.date).pivot_table(index='day', columns='email', values='cost', aggfunc='sum', fill_value=0), y_label='USD', x_label='')
calls = ev[ev.action == 'model call']
c2.subheader('By model')
c2.dataframe(calls.groupby(calls.detail.map(lambda d: (d or {}).get('model', '?'))).cost.sum().rename('Cost').rename_axis('Model').sort_values(ascending=False),
             column_config={'Cost': st.column_config.NumberColumn(format='$%.2f')})

st.subheader('Activity')
act = ev[ev.action != 'model call'].head(300)
st.dataframe(pd.DataFrame({'When': act.time.dt.strftime('%d %b, %H:%M'), 'Who': act.email, 'What': act.action,
                           'Run': act.run_id.map(lambda r: f'#{int(r)}' if pd.notna(r) else ''),
                           'Details': act.detail.map(lambda d: ' · '.join(f'{k}: {v}' for k, v in (d or {}).items()))}), hide_index=True)
st.download_button('Download all events of this period (CSV)', ev.to_csv(index=False), f'usage_last_{days}_days.csv', mime='text/csv',
                   help='Every event, including each model call with its tokens and cost.')
