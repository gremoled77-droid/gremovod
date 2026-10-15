"""Output-only API comparison, using OpenAI's public calculator (2026-10-15).

This is a hypothetical explicit API quality, never a claim about native chat usage.
Source: https://developers.openai.com/api/docs/guides/image-generation
Archived calculator: docs/official-prompts/openai-image-token-calculator.js
"""
import math

PRICE_PER_MILLION = 30.0
SOURCE = 'https://developers.openai.com/api/docs/guides/image-generation'

def api_equivalent(width, height, model='gpt-image-2.5'):
    assumed_size = not (isinstance(width,int) and isinstance(height,int) and width>0 and height>0
                        and width%16==0 and height%16==0 and max(width,height)<=3840
                        and max(width,height)/min(width,height)<=3 and 655360<=width*height<=8294400)
    if assumed_size:width,height=1536,1024
    # Both GPT Image 2 high and 2.5 max use the same base grid in the official calculator.
    quality='high' if model=='gpt-image-2' else 'max'
    long_grid=96
    short_grid=round(long_grid*min(width,height)/max(width,height))
    tokens=math.ceil(long_grid*short_grid*(2_000_000+width*height)/4_000_000)
    return {'usd':round(tokens*PRICE_PER_MILLION/1_000_000,6),'output_tokens_estimate':tokens,
            'width':width,'height':height,'assumed_size':assumed_size,'quality_assumption':quality,
            'model_assumption':model,'input_cost_included':False,'source':SOURCE,'verified_at':'2026-10-15'}
