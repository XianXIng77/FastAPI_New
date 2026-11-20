# ui

## Project setup
```
npm install
```

### Compiles and hot-reloads for development
```
npm run dev
```

Use relative URLs such as `/auth/me` for authentication requests. The dev server forwards `/auth/*` to FastAPI at `http://127.0.0.1:810` and preserves the request path. If you start FastAPI on a different port, set `VUE_APP_BACKEND_URL` before running `npm run dev`.

### Compiles and minifies for production
```
npm run build
```

### Lints and fixes files
```
npm run lint
```

### Customize configuration
See [Configuration Reference](https://cli.vuejs.org/config/).
