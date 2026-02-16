// Enhanced function call highlighting for documentation
document.addEventListener('DOMContentLoaded', function() {
    console.log('Function highlighting script loaded');
    
    // Clear any corrupted content first
    function clearCorruptedContent() {
        console.log('Clearing any corrupted content...');
        const allElements = document.querySelectorAll('*');
        allElements.forEach(function(element) {
            // Remove the processed flag so everything can be re-processed cleanly
            if (element.dataset.processed) {
                delete element.dataset.processed;
            }
            
            // Fix any corrupted text content that has repeated spans
            if (element.innerHTML && element.innerHTML.includes('js-equals">=')) {
                console.log('Found corrupted element, resetting...', element);
                // Try to restore from textContent if possible
                const text = element.textContent || element.innerText;
                if (text && text.length < element.innerHTML.length * 0.5) {
                    // If text content is much shorter than HTML, the HTML is likely corrupted
                    element.innerHTML = text;
                }
            }
        });
    }
    
    // Run cleanup first
    clearCorruptedContent();
    
    /**
     * Centralized Color Configuration System
     * 
     * This system reads syntax highlighting colors from CSS custom properties defined in extra.css.
     * To change colors, modify the CSS variables in the :root section of extra.css:
     * 
     * :root {
     *     --syntax-keyword: #C586C0;     // Keywords (def, class, import)
     *     --syntax-function: #DCDCAA;    // Function names and calls
     *     --syntax-string: #CE9178;      // Strings
     *     --syntax-number: #B5CEA8;      // Numbers
     *     --syntax-comment: #6A9955;     // Comments
     *     --syntax-builtin: #569CD6;     // Built-ins (print, len)
     *     --syntax-variable: #D4D4D4;    // Variables
     *     --syntax-class: #4EC9B0;       // Class names
     *     --syntax-operator: #D4D4D4;    // Operators
     *     --syntax-punctuation: #D4D4D4; // Punctuation
     *     --syntax-error: #F44747;       // Errors
     *     --syntax-attribute: #92C5F8;   // Attributes
     * }
     * 
     * The JavaScript will automatically pick up these colors and use them for dynamic highlighting.
     */
    const SyntaxColors = {
        // Get CSS custom property value
        getCSSVariable: function(varName) {
            return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
        },
        
        // Initialize colors from CSS variables
        init: function() {
            this.keyword = this.getCSSVariable('--syntax-keyword') || '#C586C0';
            this.function = this.getCSSVariable('--syntax-function') || '#DCDCAA';
            this.string = this.getCSSVariable('--syntax-string') || '#CE9178';
            this.number = this.getCSSVariable('--syntax-number') || '#B5CEA8';
            this.comment = this.getCSSVariable('--syntax-comment') || '#6A9955';
            this.builtin = this.getCSSVariable('--syntax-builtin') || '#569CD6';
            this.variable = this.getCSSVariable('--syntax-variable') || '#D4D4D4';
            this.variableBright = this.getCSSVariable('--syntax-variable-bright') || '#E8E8E8';
            this.variableAssigned = this.getCSSVariable('--syntax-variable-assigned') || '#569CD6';
            this.parameter = this.getCSSVariable('--syntax-parameter') || '#E8D4B0';
            this.class = this.getCSSVariable('--syntax-class') || '#4EC9B0';
            this.operator = this.getCSSVariable('--syntax-operator') || '#D4D4D4';
            this.punctuation = this.getCSSVariable('--syntax-punctuation') || '#D4D4D4';
            this.error = this.getCSSVariable('--syntax-error') || '#F44747';
            this.attribute = this.getCSSVariable('--syntax-attribute') || '#92C5F8';
            
            console.log('Syntax colors initialized:', {
                keyword: this.keyword,
                function: this.function,
                string: this.string,
                number: this.number,
                comment: this.comment,
                builtin: this.builtin,
                variable: this.variable,
                variableBright: this.variableBright,
                variableAssigned: this.variableAssigned,
                parameter: this.parameter,
                class: this.class,
                operator: this.operator,
                punctuation: this.punctuation,
                error: this.error,
                attribute: this.attribute
            });
        },
        
        // Utility method to refresh colors (useful for dynamic theme changes)
        refresh: function() {
            console.log('Refreshing syntax colors...');
            this.init();
        },
        
        // Utility method to get color by semantic name
        getColor: function(colorType) {
            const colorMap = {
                'keyword': this.keyword,
                'function': this.function,
                'string': this.string,
                'number': this.number,
                'comment': this.comment,
                'builtin': this.builtin,
                'variable': this.variable,
                'variableBright': this.variableBright,
                'variableAssigned': this.variableAssigned,
                'parameter': this.parameter,
                'class': this.class,
                'operator': this.operator,
                'punctuation': this.punctuation,
                'error': this.error,
                'attribute': this.attribute
            };
            return colorMap[colorType] || this.variable; // fallback to variable color
        },
        
        // Utility method to log current color scheme (for debugging)
        logColors: function() {
            console.table({
                'Keywords (def, class, import)': this.keyword,
                'Function names and calls': this.function,
                'Strings': this.string,
                'Numbers': this.number,
                'Comments': this.comment,
                'Built-ins (print, len)': this.builtin,
                'Variables': this.variable,
                'Class names': this.class,
                'Operators': this.operator,
                'Punctuation': this.punctuation,
                'Errors': this.error,
                'Attributes': this.attribute
            });
        }
    };
    
    // Make SyntaxColors globally available for debugging
    window.SyntaxColors = SyntaxColors;
    
    // Initialize color configuration
    SyntaxColors.init();
    
    // Function to enhance syntax highlighting for function calls
    function enhanceFunctionHighlighting() {
        // Try multiple selectors to find code blocks - expanded list for API reference
        const selectors = [
            '.doc-content pre code',
            '.doc-content .highlight pre code',
            '.doc-content .highlight code',
            'pre code', 
            '.highlight pre code',
            '.highlight code',
            '.highlight',
            'code',
            '[class*="highlight"]',
            '[class*="code"]',
            '.codehilite',
            '.codehilite code',
            'div[class*="highlight"] code',
            'div[class*="codehilite"] code'
        ];
        
        let codeBlocks = [];
        let selectorUsed = '';
        
        // Try each selector and collect all matching elements
        let allCodeBlocks = new Set();
        
        for (let selector of selectors) {
            const blocks = document.querySelectorAll(selector);
            blocks.forEach(block => allCodeBlocks.add(block));
        }
        
        codeBlocks = Array.from(allCodeBlocks);
        
        console.log('Found', codeBlocks.length, 'total unique code blocks');
        console.log('Available elements:', document.querySelectorAll('pre').length, 'pre tags,', document.querySelectorAll('code').length, 'code tags');
        
        codeBlocks.forEach(function(codeBlock, index) {
            console.log('Processing code block', index, ':', codeBlock.className, codeBlock.innerHTML.substring(0, 100));
            // Get the text content
            const code = codeBlock.textContent || codeBlock.innerText;
            
            // Expand detection criteria - look for more Python-like patterns
            const looksLikePython = code.includes('def ') || 
                                   code.includes('(') || 
                                   code.includes('.') ||
                                   code.includes('=') ||
                                   code.includes('[') ||
                                   code.includes('get_') ||
                                   code.includes('set_') ||
                                   code.includes('import') ||
                                   code.includes('print(');
             
             if (!looksLikePython) {
                 console.log('Skipping block', index, '- does not look like Python code');
                 return;
             }
            
            // Find all spans with class 'n' (name tokens)
            const nameSpans = codeBlock.querySelectorAll('span.n, .highlight span.n, span[class*="n"], .highlight span[class*="n"]');
            console.log('Found', nameSpans.length, 'name spans in block', index);
            
            nameSpans.forEach(function(span, spanIndex) {
                const spanText = span.textContent || span.innerText;
                const nextSibling = span.nextElementSibling;
                const prevSibling = span.previousElementSibling;
                
                console.log('Span', spanIndex, ':', spanText, 'class:', span.className, 'next:', nextSibling?.textContent, 'prev:', prevSibling?.textContent);
                
                // Check if we're in a function signature
                const isInSignature = span.closest('.doc-signature') || 
                                    span.closest('[class*="signature"]') ||
                                    (codeBlock.textContent && codeBlock.textContent.includes('->') && codeBlock.textContent.includes(':'));
                
                if (isInSignature) {
                    // In function signatures, only highlight parameter names
                    // Parameter names are specifically: identifier followed by colon
                    // NOT: identifier that comes after colon (that's a type hint)
                    
                    const parentText = span.parentElement ? span.parentElement.textContent : '';
                    const spanStart = parentText.indexOf(spanText);
                    const beforeSpanInParent = parentText.substring(0, spanStart);
                    const afterSpanInParent = parentText.substring(spanStart + spanText.length);
                    
                    // Check if this looks like a parameter name (comes before colon, not after)
                    const isParameterName = afterSpanInParent.trim().startsWith(':') && 
                                          !beforeSpanInParent.trim().endsWith(':');
                    
                    if (isParameterName) {
                        span.className = 'js-variable-bright';
                        return;
                    }
                    
                    // For function signatures, don't apply other highlighting to anything else
                    return;
                }
                
                // Check if this looks like a function call (followed by parentheses)
                if (nextSibling && nextSibling.textContent === '(') {
                    span.style.color = SyntaxColors.function; // Function color for function calls
                    span.style.fontWeight = '500';
                    return;
                }
                
                // Check if this is a method call (preceded by dot)
                if (prevSibling && prevSibling.textContent === '.') {
                    span.style.color = SyntaxColors.function; // Function color for method calls  
                    span.style.fontWeight = '500';
                    return;
                }
                
                
                // Check if this is part of a function definition
                const prevPrevSibling = prevSibling ? prevSibling.previousElementSibling : null;
                if (prevPrevSibling && prevPrevSibling.textContent === 'def') {
                    span.style.color = SyntaxColors.function; // Function color for function definitions
                    span.style.fontWeight = 'bold';
                    return;
                }
                
                // Enhanced variable detection for API reference examples
                const parentLine = span.parentElement;
                if (parentLine) {
                    const lineText = parentLine.textContent || parentLine.innerText;
                    const spanIndex = lineText.indexOf(spanText);
                    const beforeSpan = lineText.substring(0, spanIndex);
                    const afterSpan = lineText.substring(spanIndex + spanText.length);
                    const fullLine = lineText.trim();
                    
                    // Check if this is a function parameter (in function definition)
                    if (beforeSpan.includes('def ') && (beforeSpan.includes('(') || afterSpan.includes(')'))) {
                        span.className = 'js-variable-parameter';
                        return;
                    }
                    
                    // Check if this variable is being assigned from a function call
                    // Look for patterns like: variable = function() or variable, other = function()
                    const lineHasFunctionCall = fullLine.includes('(') && fullLine.includes(')');
                    const equalsIndex = fullLine.indexOf('=');
                    
                    if (lineHasFunctionCall && equalsIndex > -1) {
                        // Get the part of the line before the = sign
                        const leftSideOfEquals = fullLine.substring(0, equalsIndex).trim();
                        // Check if this variable name appears in the left side
                        const variableInLeftSide = leftSideOfEquals.includes(spanText);
                        
                        // Additional check: make sure it's a complete word match, not a substring
                        const wordBoundaryRegex = new RegExp(`\\b${spanText}\\b`);
                        const isCompleteWordMatch = wordBoundaryRegex.test(leftSideOfEquals);
                        
                        if (variableInLeftSide && isCompleteWordMatch) {
                            span.className = 'js-variable-assigned';
                            return;
                        }
                    }
                    
                    // Check if this is a variable being used in array indexing or function calls
                    const isInArrayIndex = afterSpan.includes('[') || beforeSpan.includes('[');
                    const isInComparison = afterSpan.includes(' ==') || afterSpan.includes(' !=') || 
                                          beforeSpan.includes('== ') || beforeSpan.includes('!= ');
                    const isInFunctionCall = afterSpan.includes('(') || 
                                            (afterSpan.includes(',') && beforeSpan.includes('('));
                    
                    if (isInArrayIndex || isInComparison || isInFunctionCall) {
                        span.style.color = SyntaxColors.variableBright; // Bright variable color for used variables
                        return;
                    }
                    
                    
                    // If preceded by assignment or is at start of line, likely a variable
                    if (beforeSpan.trim().endsWith('=') || beforeSpan.trim() === '' || beforeSpan.trim().endsWith(',')) {
                        span.style.color = SyntaxColors.variable; // Variable color for variables
                        return;
                    }
                    
                    // Default: if no specific pattern matched but it's in a code block, make it at least visible
                    const currentColor = window.getComputedStyle(span).color;
                    if (currentColor === 'rgb(0, 0, 0)' || currentColor === 'black' || currentColor === 'rgba(0, 0, 0, 1)') {
                        span.style.color = SyntaxColors.variable; // Default variable color instead of black
                    }
                }
            });
            
            // Also enhance some specific patterns
            enhanceSpecificPatterns(codeBlock);
            
            // Apply specific punctuation coloring
            enhancePunctuationColors(codeBlock);
        });
    }
    
    function enhanceSpecificPatterns(codeBlock) {
        // Skip if already processed to prevent infinite loops
        if (codeBlock.dataset.processed === 'true') {
            return;
        }
        
        // Skip if this is a function signature
        const isSignatureBlock = codeBlock.closest('.doc-signature') || 
                                codeBlock.closest('[class*="signature"]') ||
                                codeBlock.classList.contains('doc-signature') ||
                                codeBlock.className.includes('signature');
        
        if (isSignatureBlock) {
            console.log('Skipping signature block for specific patterns');
            return;
        }
        
        // Get the text content only, not HTML
        let text = codeBlock.textContent || codeBlock.innerText;
        
        // Only process if it looks like Python code
        if (!text.includes('(') && !text.includes('def') && !text.includes('=')) {
            return;
        }
        
        // Work with the original HTML but be very careful about replacements
        let html = codeBlock.innerHTML;
        let originalHtml = html;
        
        
        // More general pattern for method calls after dots - simple approach
        if (!html.includes('js-function-highlight')) {
            html = html.replace(/(\.)([a-zA-Z_][a-zA-Z0-9_]*)(?=\s*\()/g, `$1<span style="color: ${SyntaxColors.function}; font-weight: 500;">$2</span>`);
        }
        
        // Pattern for function definitions - simple approach
        if (!html.includes('def ')) {
            html = html.replace(/(def\s+)([a-zA-Z_][a-zA-Z0-9_]*)/g, `$1<span style="color: ${SyntaxColors.function}; font-weight: bold;">$2</span>`);
        }
        
        // VERY CAREFUL punctuation highlighting - only if not already processed
        if (!html.includes('js-paren') && !html.includes('js-equals') && !html.includes('js-colon')) {
            // Replace punctuation more carefully - work with text content first
            // Split by HTML tags and only process text portions
            const parts = html.split(/(<[^>]*>)/);
            let newHtml = '';
            
            for (let i = 0; i < parts.length; i++) {
                let part = parts[i];
                
                // If this part is an HTML tag, leave it unchanged
                if (part.startsWith('<') && part.endsWith('>')) {
                    newHtml += part;
                } else {
                    // This is text content - apply punctuation highlighting
                    // Parentheses - make them yellow
                    part = part.replace(/(\(|\))/g, `<span class="js-paren">$1</span>`);
                    
                    // Square brackets - make them white
                    part = part.replace(/(\[|\])/g, `<span class="js-bracket">$1</span>`);
                    
                    // Equals signs with spaces around them - make them white
                    part = part.replace(/\s(==|!=)\s/g, ` <span class="js-equals">$1</span> `);
                    part = part.replace(/\s(=)\s/g, ` <span class="js-equals">$1</span> `);
                    
                    // Colons - make them white (improved regex to catch more cases)
                    part = part.replace(/(:)/g, `<span class="js-colon">$1</span>`);
                    
                    // Commas - make them white
                    part = part.replace(/(,)/g, `<span class="js-comma">$1</span>`);
                    
                    // Dots in method calls - make them white
                    part = part.replace(/(\.)(?=[a-zA-Z_])/g, `<span class="js-dot">$1</span>`);
                    
                    // Comments - highlight Python comments in muted green
                    part = part.replace(/(#.*$)/gm, `<span style="color: ${SyntaxColors.comment}; font-style: italic; opacity: 0.9;">$1</span>`);
                    
                    newHtml += part;
                }
            }
            
            html = newHtml;
        }
        
        if (html !== originalHtml) {
            codeBlock.innerHTML = html;
            console.log('Applied text replacements to code block');
        }
        
        // Mark as processed to prevent re-processing
        codeBlock.dataset.processed = 'true';
    }
    
    // Enhanced punctuation highlighting function
    function enhancePunctuationColors(codeBlock) {
        // Skip if this is a function signature
        const isSignatureBlock = codeBlock.closest('.doc-signature') || 
                                codeBlock.closest('[class*="signature"]') ||
                                codeBlock.classList.contains('doc-signature') ||
                                codeBlock.className.includes('signature');
        
        if (isSignatureBlock) {
            console.log('Skipping signature block for punctuation coloring');
            return;
        }
        
        // Find all spans with punctuation and operator classes
        const punctuationSpans = codeBlock.querySelectorAll('.highlight .p, .highlight .o, .hljs-punctuation, .hljs-operator');
        
        punctuationSpans.forEach(function(span) {
            const text = span.textContent || span.innerText;
            
            // Color parentheses yellow
            if (text === '(' || text === ')') {
                span.style.color = SyntaxColors.function;
            }
            // Color square brackets white
            else if (text === '[' || text === ']') {
                span.style.color = 'white';
            }
            // Color equals signs and colons white
            else if (text === '=' || text === '==' || text === '!=' || text === ':') {
                span.style.color = 'white';
            }
            // Color commas white
            else if (text === ',') {
                span.style.color = 'white';
            }
            // Color dots white
            else if (text === '.') {
                span.style.color = 'white';
            }
        });
    }
    
    // Fallback: Simple text replacement on all content
    function simpleTextHighlighting() {
        console.log('Running simple text highlighting fallback');
        
        // Find any element that might contain code - expanded list
        const possibleCodeElements = document.querySelectorAll('pre, code, .highlight, [class*="lang-"], [class*="language-"], .codehilite, div[class*="highlight"], div[class*="codehilite"]');
        console.log('Found', possibleCodeElements.length, 'possible code elements');
        
        possibleCodeElements.forEach(function(element, index) {
            // Skip if this is a function signature
            const isSignatureBlock = element.closest('.doc-signature') || 
                                    element.closest('[class*="signature"]') ||
                                    element.classList.contains('doc-signature') ||
                                    element.className.includes('signature');
            
            if (isSignatureBlock) {
                console.log('Skipping signature block', index, 'for simple text highlighting');
                return;
            }
            
            // Expanded detection criteria for API reference examples
            const hasRelevantContent = element.textContent.includes('update()') || 
                                      element.textContent.includes('SG_main') || 
                                      element.textContent.includes('def ') ||
                                      element.textContent.includes('exo_angle') ||
                                      element.textContent.includes('device_id') ||
                                      element.textContent.includes('finger_nr') ||
                                      element.textContent.includes('get_') ||
                                      element.textContent.includes('set_') ||
                                      element.textContent.includes('[') ||
                                      element.textContent.includes('=') ||
                                      element.textContent.includes('print(') ||
                                      element.textContent.includes('import');
            
            if (hasRelevantContent) {
                console.log('Processing element', index, 'with relevant content');
                
                // Use CSS class for better styling control
                console.log('Element computed style:', window.getComputedStyle(element).backgroundColor);
                
                // Try a more direct approach - replace text content directly in the element
                let html = element.innerHTML;
                let originalHtml = html;
                
                
                
                if (html !== originalHtml) {
                    element.innerHTML = html;
                    console.log('Applied CSS class highlighting to element', index);
                    
                    // Also apply punctuation coloring
                    enhancePunctuationColors(element);
                    
                    // Force reflow to apply styles
                    setTimeout(function() {
                        const highlights = element.querySelectorAll('.js-function-highlight, .js-variable-highlight');
                        console.log('Found', highlights.length, 'highlighted elements');
                        highlights.forEach(function(highlight, i) {
                            const computedStyle = window.getComputedStyle(highlight);
                            console.log('Highlight', i, ':', highlight.textContent);
                            console.log('  - background:', computedStyle.backgroundColor);
                            console.log('  - color:', computedStyle.color);
                            console.log('  - classes:', highlight.className);
                            console.log('  - element:', highlight.tagName);
                        });
                    }, 100);
                }
                
                // Apply punctuation coloring even if no function highlighting was applied
                enhancePunctuationColors(element);
                
                console.log('Applied simple highlighting to element', index);
            }
        });
    }
    
    // Run both approaches with delays to ensure content is loaded
    setTimeout(enhanceFunctionHighlighting, 100);
    setTimeout(simpleTextHighlighting, 200);
    setTimeout(enhanceFunctionHighlighting, 500);
    setTimeout(simpleTextHighlighting, 600);
    setTimeout(enhanceFunctionHighlighting, 1000);
    setTimeout(simpleTextHighlighting, 1100);
    
    // Re-run after any dynamic content loads
    const observer = new MutationObserver(function(mutations) {
        let shouldRerun = false;
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                shouldRerun = true;
            }
        });
        if (shouldRerun) {
            setTimeout(enhanceFunctionHighlighting, 100);
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}); 