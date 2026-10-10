import { expect, test } from '@playwright/test';

const rpcResults = {
  get_app_settings: { show_covers: false },
  get_autohotspot_status: 'inactive',
  get_disk_usage: { used: 8_000, total: 32_000 },
  get_folder_content: [
    {
      name: 'Albums',
      relpath: 'Music/Rock/Albums',
      type: 'directory',
    },
    {
      name: 'sample.mp3',
      relpath: 'Music/Rock/sample.mp3',
      type: 'file',
    },
  ],
  get_ip_address: '192.168.1.42',
  get_outputs: {
    active_sink: 'speaker',
    sink_list: [
      { alias: 'Built-in speaker', pulse_sink_name: 'speaker' },
      { alias: 'USB audio', pulse_sink_name: 'usb' },
    ],
  },
  get_soft_max_volume: 80,
  get_state: {
    enabled: false,
    remaining_seconds: 0,
    running: false,
  },
  get_volume: 42,
  get_single_coverart: 'test-cover.png',
  list_albums: [
    { albumartist: 'Daft Punk', album: ['Discovery', 'Random Access Memories'] },
    { albumartist: 'Massive Attack', album: 'Mezzanine' },
  ],
  list_songs_by_artist_and_album: [
    {
      album: 'Bedtime Stories',
      artist: 'Storyteller',
      duration: 180,
      file: 'service:track:chapter-one',
      provider: 'streaming',
      title: 'Chapter One',
      track: '1',
    },
  ],
  list_cards: {
    '0001234567': {
      action: { args: [] },
      from_alias: '',
      func: 'play',
    },
  },
};

const socketEvents = {
  'batt_status': { charging: false, soc: 76 },
  'core.plugins.loaded': { battmon: true },
  'core.version': '3.7.0-alpha',
  'host.temperature.cpu': '47.2',
  'host.timer.cputemp': { enabled: true },
  'playerstatus': {
    album: 'Discovery',
    artist: 'Daft Punk',
    duration: '224',
    elapsed: '42',
    file: 'Daft Punk/Discovery/One More Time.mp3',
    random: '0',
    repeat: '0',
    single: '0',
    songid: '1',
    state: 'play',
    title: 'One More Time',
  },
  'volume.level': { mute: false, volume: 42 },
};

async function mockBackend(
  page,
  {
    failRpc = false,
    rpcGate,
    showCovers = false,
    spotify = false,
    streamingLibrary = false,
    timerEvents = {},
  } = {},
) {
  const eventSockets = new Set();
  const libraryCalls = [];
  const rpcCalls = [];
  const subscribedTopics = new Set();

  await page.addInitScript(() => {
    window.localStorage.setItem('i18nextLng', 'en');
  });

  await page.route('**/api/v1/library/entries**', async route => {
    const requestUrl = new URL(route.request().url());
    libraryCalls.push(requestUrl.searchParams.get('folder'));
    await route.fulfill({
      body: JSON.stringify({
        entries: rpcResults.get_folder_content,
      }),
      contentType: 'application/json',
      status: 200,
    });
  });

  await page.route('**/api/v1/rpc', async route => {
    const request = route.request();
    const payload = request.postDataJSON();
    rpcCalls.push(payload);

    if (rpcGate) {
      await rpcGate;
    }

    if (failRpc) {
      await route.fulfill({
        body: JSON.stringify({ error: 'Backend unavailable' }),
        contentType: 'application/json',
        status: 503,
      });
      return;
    }

    const key = payload.method || payload.plugin;
    let result = rpcResults[key] ?? null;
    if (key === 'get_app_settings') {
      result = { show_covers: showCovers };
    }
    if (key === 'list_library_sources') {
      result = [
        {
          id: 'mpd',
          label: 'Local',
          views: [
            {
              id: 'albums',
              label: 'Albums',
              kind: 'items',
              content_types: ['album'],
            },
            {
              id: 'folders',
              label: 'Folders',
              kind: 'folders',
              content_types: [],
            },
          ],
        },
        ...(spotify ? [{
          id: 'spotify',
          label: 'Spotify',
          views: [
            {
              id: 'playlists',
              label: 'Playlists',
              kind: 'items',
              content_types: ['playlist'],
            },
            {
              id: 'albums',
              label: 'Albums',
              kind: 'items',
              content_types: ['album'],
            },
          ],
        }] : []),
        ...(streamingLibrary ? [{
          id: 'streaming',
          label: 'Streaming',
          views: [
            {
              id: 'playlists',
              label: 'Playlists',
              kind: 'items',
              content_types: ['playlist'],
            },
          ],
        }] : []),
      ];
    }
    if (key === 'list_backends') {
      result = ['mpd', ...(spotify ? ['spotify'] : [])];
    }
    if (key === 'auth_status' || key === 'set_client_id') {
      result = {
        client_id_configured: key === 'set_client_id',
        go_librespot_connected: true,
        web_api_connected: false,
      };
    }
    if (key === 'search' && payload.plugin === 'spotify') {
      result = [
        {
          album: 'Discovery',
          artists: ['Daft Punk'],
          cover_url: null,
          duration_ms: 320000,
          name: 'One More Time',
          type: 'track',
          uri: 'spotify:track:0DiWol3AO6WpXZgp0goxAV',
        },
        {
          album: 'Discovery',
          artists: ['Daft Punk'],
          cover_url: null,
          name: 'Discovery',
          type: 'album',
          uri: 'spotify:album:2noRn2Aes5aoNVsU6iWThc',
        },
        {
          album: null,
          artists: ['Someone'],
          cover_url: null,
          name: 'Daft Punk Mix',
          tracks_available: false,
          type: 'playlist',
          uri: 'spotify:playlist:mix',
        },
      ];
    }
    if (key === 'list_songs_by_artist_and_album' && payload.kwargs.content_uri === 'spotify:playlist:theirs') {
      result = [];
    }
    if (key === 'list_library_items') {
      const localItems = rpcResults.list_albums.flatMap(entry => (
        (Array.isArray(entry.album) ? entry.album : [entry.album]).map(album => ({
          ...entry,
          album,
          content_type: 'album',
          provider: 'mpd',
        }))
      ));
      const spotifyItems = spotify ? [
        {
          albumartist: 'Me',
          album: 'Road Trip',
          content_type: 'playlist',
          content_uri: 'spotify:playlist:mine',
          provider: 'spotify',
          tracks_available: true,
        },
        {
          albumartist: 'triple j',
          album: 'Hottest 100',
          content_type: 'playlist',
          content_uri: 'spotify:playlist:theirs',
          provider: 'spotify',
          tracks_available: false,
        },
      ] : [];
      const streamingItems = streamingLibrary ? [{
        albumartist: 'Family',
        album: 'Bedtime Stories',
        content_type: 'playlist',
        content_uri: 'service:playlist:bedtime',
        provider: 'streaming',
      }] : [];
      result = [...localItems, ...spotifyItems, ...streamingItems].filter(item => (
        (!payload.kwargs.provider || item.provider === payload.kwargs.provider) &&
        (
          !payload.kwargs.content_types ||
          payload.kwargs.content_types.includes(item.content_type)
        )
      ));
    }
    await route.fulfill({
      body: JSON.stringify({
        id: payload.id,
        result,
      }),
      contentType: 'application/json',
      status: 200,
    });
  });

  await page.route('**/cover-cache/test-cover.png', route => route.fulfill({
    contentType: 'image/png',
    path: 'public/logo192.png',
    status: 200,
  }));

  await page.routeWebSocket('**/api/v1/events', socket => {
    eventSockets.add(socket);
    socket.onMessage(message => {
      const payload = JSON.parse(message);
      if (payload.type !== 'subscribe') {
        return;
      }

      payload.topics.forEach(topic => {
        subscribedTopics.add(topic);
        const events = { ...socketEvents, ...timerEvents };
        if (topic in events) {
          socket.send(JSON.stringify({
            type: 'event',
            topic,
            data: events[topic],
          }));
        }
      });
    });
  });

  const publishEvent = (topic, data) => {
    eventSockets.forEach(socket => {
      socket.send(JSON.stringify({
        type: 'event',
        topic,
        data,
      }));
    });
  };

  return {
    libraryCalls,
    publishEvent,
    rpcCalls,
    subscribedTopics,
  };
}

async function expectStableLayout(page) {
  await expect(page.locator('#root')).not.toBeEmpty();
  await expect(page.locator('.MuiBottomNavigation-root')).toBeVisible();

  const layout = await page.evaluate(() => {
    const actions = Array.from(
      document.querySelectorAll('.MuiBottomNavigationAction-root'),
      element => element.getBoundingClientRect(),
    );
    const nav = document.querySelector('.MuiBottomNavigation-root')
      .getBoundingClientRect();
    const actionRows = Array.from(document.querySelectorAll('.MuiListItem-root'));

    return {
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
      navWithinViewport: nav.top >= 0 && nav.bottom <= window.innerHeight + 1,
      overlappingContentActions: actionRows.some(row => {
        const text = row.querySelector('.MuiListItemText-root');
        const action = row.querySelector(
          '.MuiButton-root, .MuiIconButton-root, .MuiSwitch-root',
        );
        if (!text || !action) {
          return false;
        }

        const textRect = text.getBoundingClientRect();
        const actionRect = action.getBoundingClientRect();
        return (
          textRect.left < actionRect.right &&
          textRect.right > actionRect.left &&
          textRect.top < actionRect.bottom &&
          textRect.bottom > actionRect.top
        );
      }),
      overlappingActions: actions.some((action, index) => (
        actions.slice(index + 1).some(other => (
          action.left < other.right &&
          action.right > other.left &&
          action.top < other.bottom &&
          action.bottom > other.top
        ))
      )),
    };
  });

  expect(layout).toEqual({
    horizontalOverflow: false,
    navWithinViewport: true,
    overlappingContentActions: false,
    overlappingActions: false,
  });
}

async function expectAbove(top, bottom) {
  const [topBox, bottomBox] = await Promise.all([
    top.boundingBox(),
    bottom.boundingBox(),
  ]);

  expect(topBox.y + topBox.height).toBeLessThanOrEqual(bottomBox.y);
}

function collectConsoleErrors(page) {
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error') {
      errors.push(message.text());
    }
  });
  return errors;
}

const routes = [
  {
    name: 'player',
    path: '/',
    ready: '#player',
    text: 'One More Time',
  },
  {
    name: 'library',
    path: '/#/library',
    ready: '#library',
    text: 'Discovery',
  },
  {
    name: 'cards',
    path: '/#/cards',
    ready: '#cards',
    text: '0001234567',
  },
  {
    name: 'settings',
    path: '/#/settings',
    ready: '#settings',
    text: '192.168.1.42',
  },
];

for (const route of routes) {
  test(`${route.name} route renders`, async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    await mockBackend(page);
    await page.goto(route.path);
    await expect(page.locator(route.ready)).toBeVisible();
    await expect(page.getByText(route.text, { exact: false }).first()).toBeVisible();
    await expectStableLayout(page);
    if (route.name === 'library') {
      await expectAbove(
        page.getByRole('tab', { name: 'Overview' }),
        page.getByText('Discovery', { exact: true }),
      );
    }
    if (route.name === 'cards') {
      await expectAbove(
        page.getByRole('heading', { name: 'Cards' }),
        page.getByText('0001234567', { exact: true }),
      );
    }
    await expect(page).toHaveScreenshot(`${route.name}.png`);
    expect(consoleErrors).toEqual([]);
  });
}

test('bottom navigation changes routes', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await mockBackend(page);
  await page.goto('/');

  await page.getByRole('link', { name: 'Library' }).click();
  await expect(page).toHaveURL(/#\/library\/overview$/);

  await page.getByRole('link', { name: 'Cards' }).click();
  await expect(page).toHaveURL(/#\/cards$/);

  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page).toHaveURL(/#\/settings$/);
  expect(consoleErrors).toEqual([]);
});

test('player backdrop covers its full width across the md breakpoint', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop');
  const consoleErrors = collectConsoleErrors(page);
  await page.setViewportSize({ width: 800, height: 800 });
  await mockBackend(page, { showCovers: true });
  await page.goto('/');

  await expect(page.locator('#player img')).toBeVisible();
  for (const width of [800, 899, 900]) {
    await page.setViewportSize({ width, height: 800 });
    const [playerBox, backdropBox] = await Promise.all([
      page.locator('#player').boundingBox(),
      page.getByTestId('player-backdrop').boundingBox(),
    ]);

    expect(backdropBox.x).toBeCloseTo(playerBox.x, 0);
    expect(backdropBox.width).toBeCloseTo(playerBox.width, 0);
    expect(playerBox.width).toBeCloseTo(width < 900 ? width : width / 2, 0);
  }

  await page.setViewportSize({ width: 899, height: 800 });
  await expect(page).toHaveScreenshot('player-899.png');
  expect(consoleErrors).toEqual([]);
});

test('encoded library folder routes preserve the folder path', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const { libraryCalls } = await mockBackend(page);
  await page.goto('/#/library/folders/Music%2FRock');

  await expect.poll(() => libraryCalls).toContain('Music/Rock');
  await expect(page).toHaveURL(/#\/library\/mpd\/folders\/Music%2FRock$/);
  await expect(page.getByRole('link', { name: 'Library' })).toHaveClass(/Mui-selected/);
  await expect(page.getByText('sample.mp3')).toBeVisible();
  await expectStableLayout(page);
  expect(consoleErrors).toEqual([]);
});

test('local library tabs replace the current nested route', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await mockBackend(page);
  await page.goto('/#/library/mpd/folders/Music%2FRock?cardId=123');

  await page.getByRole('tab', { name: 'Albums' }).click();

  await expect(page).toHaveURL(/#\/library\/mpd\/albums\?cardId=123$/);
  await expect(page.getByText('Discovery', { exact: true })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test('library playback preserves provider and content URI', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const { rpcCalls } = await mockBackend(page, { streamingLibrary: true });
  await page.goto('/#/library');

  await expect(
    page.getByRole('heading', { name: 'Streaming Playlists' }),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Streaming' }).click();
  await expect(page).toHaveURL(/#\/library\/streaming\/playlists$/);

  await page.getByText('Bedtime Stories', { exact: true }).click();
  await expect(page.getByText('Chapter One', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Play' }).click();

  await expect.poll(() => (
    rpcCalls.find(call => call.method === 'play_album')?.kwargs
  )).toEqual({
    album: 'Bedtime Stories',
    albumartist: 'Family',
    content_uri: 'service:playlist:bedtime',
    provider: 'streaming',
  });
  expect(consoleErrors).toEqual([]);
});

test('Spotify search assigns provider-aware album cards', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const { rpcCalls } = await mockBackend(page, { spotify: true });
  await page.goto('/#/cards/0001234567/edit');

  await page.getByLabel('Actions').selectOption('play_music');
  await page.getByRole('textbox', { name: 'Search Spotify' }).fill('discovery');
  await page.keyboard.press('Enter');
  await expect.poll(() => (
    rpcCalls.find(call => call.method === 'search')?.kwargs
  )).toEqual({ query: 'discovery', types: 'track,album,playlist' });

  await page.getByRole('button', { name: 'Discovery' }).click();
  await expect(page.getByText('Selected album')).toBeVisible();
  await page.getByRole('button', { name: 'Save' }).click();

  await expect.poll(() => (
    rpcCalls.find(call => call.plugin === 'register_card')?.kwargs
  )).toEqual({
    args: ['Daft Punk', 'Discovery', 'spotify:album:2noRn2Aes5aoNVsU6iWThc', 'spotify'],
    card_id: '0001234567',
    cmd_alias: 'play_album',
    overwrite: true,
  });
  expect(consoleErrors).toEqual([]);
});

test('Spotify library search finds songs, albums and playlists', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const { rpcCalls } = await mockBackend(page, { spotify: true });
  await page.goto('/#/library/spotify/playlists');

  await page.getByRole('button', { name: 'Show search' }).click();
  const searchBox = page.getByRole('textbox', { name: 'Search your library and Spotify' });
  await searchBox.fill('road');
  await expect(page.getByRole('heading', { name: 'In your library' })).toBeVisible();
  await expect(page.getByText('Road Trip')).toBeVisible();

  await searchBox.fill('daft');

  await expect(page.getByRole('heading', { name: 'Songs on Spotify' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Albums on Spotify' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Playlists on Spotify' })).toBeVisible();
  await expect(page.getByText('Someone • Tracks not shared by Spotify')).toBeVisible();
  // Typing is debounced: no searches for the partial queries
  const queries = rpcCalls.filter(call => call.method === 'search').map(call => call.kwargs.query);
  expect(queries.filter(query => query === 'daft')).toHaveLength(1);
  expect(queries.filter(query => ['d', 'da', 'daf', 'r', 'ro', 'roa'].includes(query))).toEqual([]);

  await expect(page.getByRole('heading', { name: 'In your library' })).toHaveCount(0);
  await page.getByText('One More Time').click();
  await expect.poll(() => (
    rpcCalls.find(call => call.method === 'play_single')?.kwargs
  )).toEqual({ song_url: 'spotify:track:0DiWol3AO6WpXZgp0goxAV', provider: 'spotify' });

  await page.getByRole('button', { name: /^Discovery/ }).click();
  await expect(page).toHaveURL(/#\/library\/spotify\/albums\/Daft%20Punk\/Discovery\?content_uri=spotify%3Aalbum%3A2noRn2Aes5aoNVsU6iWThc/);
  expect(consoleErrors).toEqual([]);
});

test('translations load from a URL that changes with their content', async ({ page }) => {
  const localeRequests = [];
  page.on('request', request => {
    const { pathname, search } = new URL(request.url());
    if (pathname.startsWith('/locales/')) localeRequests.push(`${pathname}${search}`);
  });
  await mockBackend(page);
  await page.goto('/');

  await expect(page.getByRole('link', { name: 'Library' })).toBeVisible();
  // Regional variants like en-US don't exist and are not requested
  expect(localeRequests).toEqual([expect.stringMatching(/^\/locales\/en\/translation\.json\?v=[0-9a-f]{12}$/)]);
});

test('Spotify playlists without shared tracks can still be played', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const { rpcCalls } = await mockBackend(page, { spotify: true });
  await page.goto('/#/library/spotify/playlists');

  await expect(page.getByText('Me', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Hottest 100/ }).click();

  await expect(page.getByText("Spotify doesn't share the tracks of playlists you don't own.", { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Play' }).click();
  await expect.poll(() => (
    rpcCalls.find(call => call.method === 'play_album')?.kwargs
  )).toEqual({
    albumartist: 'triple j',
    album: 'Hottest 100',
    content_uri: 'spotify:playlist:theirs',
    provider: 'spotify',
  });
  expect(consoleErrors).toEqual([]);
});

test('Spotify search is hidden without the Spotify backend', async ({ page }) => {
  await mockBackend(page);
  await page.goto('/#/cards/0001234567/edit');

  await page.getByLabel('Actions').selectOption('play_music');

  await expect(page.getByRole('button', { name: 'Select music' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Search Spotify' })).toHaveCount(0);
});

test('Spotify settings store the client id', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const { rpcCalls } = await mockBackend(page, { spotify: true });
  await page.goto('/#/settings');

  await expect(page.getByText('go-librespot: connected')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Connect Spotify' })).toBeDisabled();
  await page.getByRole('textbox', { name: 'Client ID' }).fill(' my-client-id ');
  await page.getByRole('button', { name: 'Save client ID' }).click();

  await expect(page.getByText('Client ID saved.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Connect Spotify' })).toBeEnabled();
  expect(
    rpcCalls.find(call => call.method === 'set_client_id')?.kwargs,
  ).toEqual({ client_id: 'my-client-id' });
  expect(consoleErrors).toEqual([]);
});

test('cards with unknown songs still render their song URL', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await mockBackend(page);
  await page.route('**/api/v1/rpc', async (route, request) => {
    const payload = request.postDataJSON();
    if (payload.plugin === 'list_cards') {
      await route.fulfill({
        body: JSON.stringify({
          id: payload.id,
          result: {
            '0001234567': {
              action: { args: ['spotify:track:T', 'spotify'] },
              from_alias: 'play_single',
              func: 'play_single',
            },
          },
        }),
        contentType: 'application/json',
        status: 200,
      });
      return;
    }
    if (payload.method === 'get_song_by_url') {
      await route.fulfill({
        body: JSON.stringify({ id: payload.id, result: [] }),
        contentType: 'application/json',
        status: 200,
      });
      return;
    }
    await route.fallback();
  });
  await page.goto('/#/cards/0001234567/edit');

  await expect(page.getByText('Selected song')).toBeVisible();
  await expect(page.getByText('Unknown title')).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test('cards route shows its loading state while RPC is pending', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  let releaseRpc;
  const rpcGate = new Promise(resolve => {
    releaseRpc = resolve;
  });

  await mockBackend(page, { rpcGate });
  await page.goto('/#/cards');

  await expect(page.getByRole('progressbar')).toBeVisible();
  releaseRpc();
  await expect(page.getByText('0001234567')).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test('RPC failures leave navigation and an error state available', async ({ page }) => {
  await mockBackend(page, { failRpc: true });
  await page.goto('/#/cards');

  await expect(page.getByText('An error occurred while loading cards list.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible();
  await expectStableLayout(page);
});

test('timer settings follow authoritative backend state', async ({ page }) => {
  const timerTopic = 'timers.timer_shutdown';
  const {
    publishEvent,
    rpcCalls,
    subscribedTopics,
  } = await mockBackend(page);
  await page.goto('/#/settings');

  const shutdownTimer = page.getByRole('listitem').filter({
    has: page.getByText('Shut Down', { exact: true }),
  });
  await expect.poll(() => Array.from(subscribedTopics)).toContain(timerTopic);
  publishEvent(timerTopic, {
    enabled: true,
    remaining_seconds: 3600,
  });
  await expect(page.getByText('1:00:00')).toBeVisible();
  await shutdownTimer.getByRole('button', { name: 'Cancel' }).click();
  await expect(
    shutdownTimer.getByRole('button', { name: 'Set timer' }),
  ).toBeVisible();
  await expect.poll(() => (
    rpcCalls.filter(call => (
      call.plugin === 'timer_shutdown' && call.method === 'cancel'
    )).length
  )).toBe(1);

  publishEvent(timerTopic, {
    enabled: true,
    remaining_seconds: 7200,
  });
  await expect(page.getByText('2:00:00')).toBeVisible();

  publishEvent(timerTopic, {
    enabled: false,
    remaining_seconds: 0,
  });
  const setTimer = shutdownTimer.getByRole('button', { name: 'Set timer' });
  await expect(setTimer).toBeVisible();
  await setTimer.click();
  const slider = page.getByRole('slider');
  await slider.press('ArrowRight');
  await slider.press('ArrowRight');
  await page.getByRole('button', { name: 'Start timer' }).click();

  await expect.poll(() => (
    rpcCalls.filter(call => (
      call.plugin === 'timer_shutdown' && call.method === 'start'
    ))
  )).toHaveLength(1);
  const [startCall] = rpcCalls.filter(call => (
    call.plugin === 'timer_shutdown' && call.method === 'start'
  ));
  expect(startCall.kwargs).toEqual({ wait_seconds: 300 });
  expect(rpcCalls.filter(call => (
    call.plugin === 'timer_shutdown' && call.method === 'cancel'
  ))).toHaveLength(1);
});
