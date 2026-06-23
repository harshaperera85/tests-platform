// Single axios instance behind the generated client (Orval `mutator`).
// baseURL is empty by default so requests are same-origin and the Vite dev-server
// proxy forwards /api -> backend (no CORS, no backend change). Point at a remote
// API by setting VITE_API_BASE_URL.
import Axios, { type AxiosError, type AxiosRequestConfig } from "axios";

export const AXIOS_INSTANCE = Axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
});

export const customInstance = <T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): Promise<T> => {
  const source = Axios.CancelToken.source();
  const promise = AXIOS_INSTANCE({
    ...config,
    ...options,
    cancelToken: source.token,
  }).then(({ data }) => data as T);

  // Orval expects a cancelable promise for react-query cleanup.
  (promise as Promise<T> & { cancel?: () => void }).cancel = () =>
    source.cancel("Query was cancelled");

  return promise;
};

export default customInstance;

export type ErrorType<Error> = AxiosError<Error>;
export type BodyType<BodyData> = BodyData;
