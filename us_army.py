import requests
from bs4 import BeautifulSoup
import json
import time
import os

BASE_URL = 'https://currentops.com'
TARGET_URL = 'https://currentops.com/units/us'

output_dir = 'scrape_output'
os.makedirs(output_dir, exist_ok=True)

visited_urls = set()

SELECTORS = {
    'flat_list': '.subords-units ul a',
    'first_level': '.subords-units > li > ul > li > div:nth-child(1) > a',
    'second_level': '.subords-units > li > ul > li > div .margin-right-5px+ a',
    'third_level': '.subords-units ul ul .margin-right-5px+ a',
    'full_unit_name': '.grippy-host, .subords-units ul ul .margin-right-5px+ a',
    'location_name': '.subords-units ul ul .location a',
    'location_details': '.subords-units ul ul i'
}

def get_soup(url):
    try:
        print(f"[INFO] Fetching: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None

def has_nested_structure(soup):
    second_level_elements = soup.select(SELECTORS['second_level'])
    return len(second_level_elements) > 0

def extract_additional_info(soup):
    additional_info = {}
    
    full_unit_elements = soup.select(SELECTORS['full_unit_name'])
    if full_unit_elements:
        additional_info['full_unit_name'] = full_unit_elements[0].get_text(strip=True)
    
    location_name_elements = soup.select(SELECTORS['location_name'])
    if location_name_elements:
        additional_info['location_name'] = location_name_elements[0].get_text(strip=True)
    
    location_details_elements = soup.select(SELECTORS['location_details'])
    if location_details_elements:
        additional_info['location_details'] = location_details_elements[0].get_text(strip=True)
    
    return additional_info

def scrape_flat_structure(soup, base_url):
    flat_items = []
    elements = soup.select(SELECTORS['flat_list'])
    
    for element in elements:
        name = element.get_text(strip=True)
        href = element.get('href')
        
        if not name or href is None:
            continue
            
        if href and not href.startswith('http'):
            href = requests.compat.urljoin(base_url, href)
        
        item_soup = get_soup(href)
        additional_info = {}
        if item_soup:
            additional_info = extract_additional_info(item_soup)
        
        item = {
            'name': name,
            'url': href,
            'type': 'flat_item',
            **additional_info  
        }
        
        flat_items.append(item)
        print(f"[INFO] Found flat item: {name}")
    
    return flat_items

def scrape_nested_structure(url, depth=0, max_depth=3):
    if url in visited_urls or depth > max_depth:
        return []
    
    visited_urls.add(url)
    
    soup = get_soup(url)
    if not soup:
        return []
    
    page_info = extract_additional_info(soup)
    
    nested_items = []
    
    if depth == 0:
        selector = SELECTORS['first_level']
    elif depth == 1:
        selector = SELECTORS['second_level']
    else:
        selector = SELECTORS['third_level']
    
    elements = soup.select(selector)
    for element in elements:
        name = element.get_text(strip=True)
        href = element.get('href')
        
        if not name or href is None:
            continue
            
        if href and not href.startswith('http'):
            href = requests.compat.urljoin(BASE_URL, href)
        
        if href in visited_urls:
            continue
        
        print(f"[INFO] {'  ' * depth}Found nested item (level {depth+1}): {name}")
        
        item_soup = get_soup(href)
        additional_info = {}
        if item_soup:
            additional_info = extract_additional_info(item_soup)
        
        item = {
            'name': name,
            'url': href,
            'type': f'level_{depth+1}_item',
            **additional_info 
        }
        
        if depth < max_depth:
            if item_soup:
                if has_nested_structure(item_soup):
                    sub_items = scrape_nested_structure(href, depth + 1, max_depth)
                    if sub_items:
                        item['subunits'] = sub_items
                else:
                    flat_items = scrape_flat_structure(item_soup, href)
                    if flat_items:
                        item['subunits'] = flat_items
            
            time.sleep(0.3)
        
        nested_items.append(item)
    
    return nested_items

def scrape_main_components():
    print(f"[INFO] Starting enhanced organizational scraping from {TARGET_URL}")
    
    visited_urls.clear()
    
    soup = get_soup(TARGET_URL)
    if not soup:
        return []
    
    main_components = []
    
    a_tags = soup.select("div > a:has(h4)")
    for a_tag in a_tags:
        h4 = a_tag.find('h4')
        if h4:
            name = h4.get_text(strip=True)
            href = a_tag.get('href')
            if href and not href.startswith('http'):
                href = requests.compat.urljoin(BASE_URL, href)
            
            print(f"[INFO] Found main component: {name}")
            
            if href in visited_urls:
                continue
            
            soup_branch = get_soup(href)
            if not soup_branch:
                continue
                
            branch_info = extract_additional_info(soup_branch)
            
            component = {
                'name': name,
                'url': href,
                'type': 'main_branch',
                **branch_info  
            }
            
            subcategories = []
            sub_a_tags = soup_branch.select("div > a:has(h4)")
            
            for sub_a_tag in sub_a_tags:
                sub_h4 = sub_a_tag.find('h4')
                if sub_h4:
                    sub_name = sub_h4.get_text(strip=True)
                    sub_href = sub_a_tag.get('href')
                    if sub_href and not sub_href.startswith('http'):
                        sub_href = requests.compat.urljoin(BASE_URL, sub_href)
                    
                    print(f"[INFO]   Found subcategory: {sub_name}")
                    
                    sub_soup = get_soup(sub_href)
                    if not sub_soup:
                        continue
                        
                    subcat_info = extract_additional_info(sub_soup)
                    
                    subcategory = {
                        'name': sub_name,
                        'url': sub_href,
                        'type': 'subcategory',
                        **subcat_info  
                    }
                    
                    if has_nested_structure(sub_soup):
                        nested_items = scrape_nested_structure(sub_href)
                        if nested_items:
                            subcategory['units'] = nested_items
                    else:
                        flat_items = scrape_flat_structure(sub_soup, sub_href)
                        if flat_items:
                            subcategory['units'] = flat_items
                    
                    subcategories.append(subcategory)
                    time.sleep(0.5)  
            
            if subcategories:
                component['subcategories'] = subcategories
            
            main_components.append(component)
            time.sleep(1) 
            
            visited_urls.add(href)
    
    return main_components

components_data = scrape_main_components()

output_file = os.path.join(output_dir, 'military_organization.json')
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(components_data, f, ensure_ascii=False, indent=4)

pretty_file = os.path.join(output_dir, 'military_organization_pretty.json')
with open(pretty_file, 'w', encoding='utf-8') as f:
    json.dump(components_data, f, ensure_ascii=False, indent=4)

def count_statistics(data):
    stats = {
        'main_branches': 0,
        'subcategories': 0,
        'units': 0,
        'subunits': 0,
        'flat_items': 0,
        'with_location': 0,
        'with_full_name': 0
    }
    
    stats['main_branches'] = len(data)
    
    for branch in data:
        if 'location_name' in branch or 'location_details' in branch:
            stats['with_location'] += 1
        if 'full_unit_name' in branch:
            stats['with_full_name'] += 1
            
        subcats = branch.get('subcategories', [])
        stats['subcategories'] += len(subcats)
        
        for subcat in subcats:
            if 'location_name' in subcat or 'location_details' in subcat:
                stats['with_location'] += 1
            if 'full_unit_name' in subcat:
                stats['with_full_name'] += 1
                
            units = subcat.get('units', [])
            stats['units'] += len(units)
            
            def count_subunits(items):
                count = 0
                flat_count = 0
                location_count = 0
                fullname_count = 0
                
                for item in items:
                    if 'location_name' in item or 'location_details' in item:
                        location_count += 1
                    if 'full_unit_name' in item:
                        fullname_count += 1
                        
                    if item.get('type') == 'flat_item':
                        flat_count += 1
                    
                    subunits = item.get('subunits', [])
                    count += len(subunits)
                    
                    sub_count, sub_flat, sub_loc, sub_full = count_subunits(subunits)
                    count += sub_count
                    flat_count += sub_flat
                    location_count += sub_loc
                    fullname_count += sub_full
                
                return count, flat_count, location_count, fullname_count
            
            subunit_count, flat_count, loc_count, full_count = count_subunits(units)
            stats['subunits'] += subunit_count
            stats['flat_items'] += flat_count
            stats['with_location'] += loc_count
            stats['with_full_name'] += full_count
    
    return stats

stats = count_statistics(components_data)
print(f"\n✅ Enhanced organizational scraping complete!")
print(f"Results saved to {output_file}")
print(f"Pretty-printed version saved to {pretty_file}")
print(f"Statistics:")
print(f"  - Main branches: {stats['main_branches']}")
print(f"  - Subcategories: {stats['subcategories']}")
print(f"  - Organizational units: {stats['units']}")
print(f"  - Nested subunits: {stats['subunits']}")
print(f"  - Flat list items: {stats['flat_items']}")
print(f"  - Items with location info: {stats['with_location']}")
print(f"  - Items with full unit name: {stats['with_full_name']}")
print(f"  - Total unique URLs visited: {len(visited_urls)}")