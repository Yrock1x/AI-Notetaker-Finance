// TODO: Configure AWS Amplify with Cognito
// This file will contain the Cognito authentication configuration
// and helper functions once AWS Amplify is integrated.

// TODO: Initialize Amplify
// import { Amplify } from 'aws-amplify';
// Amplify.configure({
//   Auth: {
//     Cognito: {
//       userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID!,
//       userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID!,
//       loginWith: {
//         oauth: {
//           domain: process.env.NEXT_PUBLIC_COGNITO_DOMAIN!,
//           scopes: ['openid', 'email', 'profile'],
//           redirectSignIn: [process.env.NEXT_PUBLIC_REDIRECT_SIGN_IN!],
//           redirectSignOut: [process.env.NEXT_PUBLIC_REDIRECT_SIGN_OUT!],
//           responseType: 'code',
//         },
//       },
//     },
//   },
// });

export async function signIn(): Promise<void> {
  // TODO: Implement Cognito sign in
  console.warn("Auth not configured: signIn() is a stub");
}

export async function signOut(): Promise<void> {
  // TODO: Implement Cognito sign out
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }
  console.warn("Auth not configured: signOut() is a stub");
}

export async function getCurrentUser(): Promise<null> {
  // TODO: Implement Cognito getCurrentUser
  console.warn("Auth not configured: getCurrentUser() is a stub");
  return null;
}

export async function getAccessToken(): Promise<string | null> {
  // TODO: Implement Cognito token retrieval
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token");
  }
  return null;
}
