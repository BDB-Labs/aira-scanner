/**
 * Vercel Speed Insights initialization
 * This module imports and initializes Speed Insights for tracking web performance metrics
 * 
 * Using esm.sh CDN to load the package without a build step
 */
import { injectSpeedInsights } from 'https://esm.sh/@vercel/speed-insights@2.0.0';

// Initialize Speed Insights with default configuration
injectSpeedInsights({
  debug: false, // Set to true in development if you want to see debug logs
});
